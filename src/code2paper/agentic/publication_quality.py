"""Separate epistemic-safety and publication-utility gates for Method text."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.final_text_authorship import FinalTextAuthorshipLedgerV1
from code2paper.agentic.equation_claims import EquationClaimSetV1
from code2paper.agentic.method_argument_models import (
    ConfigurationClaimSetV1,
    MethodCompletenessMatrixV1,
    MethodSectionPlanV2,
)
from code2paper.llm.response_schemas import PublicationMethodSectionOutputV1


class PublicationQualityIssueV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    issue_id: str
    axis: Literal["epistemic_safety", "publication_utility"]
    scope: Literal["sentence", "claim", "stage", "section", "document"]
    code: str
    message: str
    section_id: str = ""
    claim_id: str = ""
    stage_id: str = ""


class EpistemicSafetyMetricsV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    authorship_gate_passed: bool
    binding_gate_passed: bool
    unsupported_positive_claims: int = 0
    source_integrity: bool = True
    final_text_validation_status: Literal["pending", "passed", "failed"] = "pending"
    support_precision: float = 1.0
    hard_gate_passed: bool


class PublicationUtilityMetricsV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    supported_unit_recall: float = 0.0
    completeness_coverage: float = 0.0
    argument_move_coverage: float = 0.0
    equation_coverage: float = 0.0
    configuration_coverage: float = 0.0
    numeric_coverage: float = 0.0
    reproducibility_detail_coverage: float = 0.0
    coherence_score: float = 1.0
    qualifier_coverage: float = 1.0
    information_density: float = 0.0
    stage_coverage: float = 0.0
    duplicate_information_rate: float = 0.0
    terminology_notation_consistent: bool = True
    editable_section_rate: float = 0.0
    paper_code_mismatch_preserved: bool = True
    content_role_status: dict[str, Literal["covered", "missing", "not_required"]] = Field(default_factory=dict)
    expert_pairwise_preference: float | None = None
    author_edit_distance: float | None = None
    utility_gate_passed: bool = False


class PublicationQualityReportV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    status: Literal["publication_ready", "incomplete", "blocked"]
    plan_gate_passed: bool
    final_integrity_gate_passed: bool
    safety: EpistemicSafetyMetricsV1
    utility: PublicationUtilityMetricsV1
    coverage_matrix: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    issues: tuple[PublicationQualityIssueV1, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "PublicationQualityReportV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        object.__setattr__(self, "content_digest", "sha256:" + hashlib.sha256(encoded).hexdigest())
        return self


def find_code_trace_prose_sections(
    section_outputs: tuple[PublicationMethodSectionOutputV1, ...]
    | list[PublicationMethodSectionOutputV1],
    *,
    fallback_text: str = "",
) -> tuple[tuple[str, str], ...]:
    """Return section-scoped prose that reads like a code execution log.

    This detector is shared by the quality report and the owning Rewrite
    route.  Keeping one detector prevents the report from flagging an issue
    that the repair path cannot see or reproduce.
    """

    surfaces = (
        [
            (str(output.section_id), str(output.section_markdown or ""))
            for output in section_outputs
        ]
        or [('', fallback_text)]
    )
    flagged: list[tuple[str, str]] = []
    for section_id, section_text in surfaces:
        if not section_text.strip():
            continue
        # Parenthetical code symbols are the intended evidence-binding form
        # (for example, "direct-current features (`self._features_dc`)").
        # Remove only those compact parentheticals before measuring whether
        # identifiers dominate the reader-facing syntax.  Bare identifiers as
        # sentence subjects and execution inventories remain visible.
        reader_surface = re.sub(
            r"\([^()\n]*`[^`\n]+`[^()\n]*\)",
            "",
            section_text,
        )
        code_tokens = re.findall(
            r"(?:self\.[A-Za-z_][A-Za-z0-9_]*|"
            r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*|"
            r"[A-Za-z_][A-Za-z0-9_]*_v\d+|[A-Za-z_][A-Za-z0-9_]*\.shape)",
            reader_surface,
        )
        section_words = len(re.findall(r"[A-Za-z0-9_]+", reader_surface))
        code_density = len(set(code_tokens)) / max(1.0, section_words / 100.0)
        self_as_subject = len(re.findall(r"\bself\.[A-Za-z_]", reader_surface))
        if code_density >= 1.2 or self_as_subject >= 3:
            flagged.append((section_id, section_text))
    return tuple(flagged)


def evaluate_publication_method_quality(
    *,
    final_text: str,
    plan: MethodSectionPlanV2,
    completeness: MethodCompletenessMatrixV1,
    section_outputs: tuple[PublicationMethodSectionOutputV1, ...] | list[PublicationMethodSectionOutputV1],
    ledger: FinalTextAuthorshipLedgerV1,
    claims: Any | None = None,
    binding_failures: tuple[str, ...] | list[str] = (),
    configurations: ConfigurationClaimSetV1 | None = None,
    equations: EquationClaimSetV1 | None = None,
    unsupported_positive_claims: int = 0,
    source_integrity: bool = True,
    open_research_requests: tuple[Any, ...] | list[Any] = (),
    utility_failures: tuple[str, ...] | list[str] = (),
    final_text_validation_status: Literal["pending", "passed", "failed"] = "passed",
    final_validation_failures: tuple[dict[str, str], ...] | list[dict[str, str]] = (),
) -> PublicationQualityReportV1:
    """Evaluate safety and writing quality without collapsing them to one score."""

    outputs = {item.section_id: item for item in section_outputs}
    units = {item.argument_unit_id: item for item in plan.argument_units}
    claims_by_id = {
        str(item.claim_id): item
        for item in (getattr(claims, "claims", ()) or ())
    }
    equation_by_id = {item.equation_id: item for item in (equations.equations if equations else ())}
    config_by_id = {
        item.configuration_id: item for item in (configurations.claims if configurations else ())
    }
    issues: list[PublicationQualityIssueV1] = []

    safety = EpistemicSafetyMetricsV1(
        authorship_gate_passed=ledger.hard_gate_passed,
        binding_gate_passed=not binding_failures,
        unsupported_positive_claims=max(0, unsupported_positive_claims),
        source_integrity=source_integrity,
        final_text_validation_status=final_text_validation_status,
        support_precision=1.0 if unsupported_positive_claims == 0 else 0.0,
        hard_gate_passed=(
            ledger.hard_gate_passed
            and not binding_failures
            and unsupported_positive_claims == 0
            and source_integrity
            and final_text_validation_status == "passed"
        ),
    )
    if not ledger.hard_gate_passed:
        issues.append(_issue("safety-authorship", "epistemic_safety", "document", "authorship_gate_failed", ", ".join(ledger.failures)))
    if final_text_validation_status != "passed":
        issues.append(_issue(
            "safety-final-text-validation", "epistemic_safety", "document",
            "final_text_validation_pending" if final_text_validation_status == "pending" else "final_text_validation_failed",
            "Final sentence-to-evidence validation has not passed.",
        ))
    # Keep the document-level gate above, but also retain the validator's
    # sentence/claim scope.  A blocked Method is only actionable when the
    # author can see which generated span needs a new Writer/Rewrite turn.
    for index, failure in enumerate(final_validation_failures):
        if not isinstance(failure, dict):
            continue
        claim_id = str(failure.get("claim_id") or "")
        section_id = str(failure.get("section_id") or "")
        message = str(failure.get("message") or "Final text claim failed reverse validation.")
        issues.append(_issue(
            f"safety-final-text-claim-{index}",
            "epistemic_safety",
            "claim" if claim_id else "sentence",
            "final_text_claim_validation_failed",
            message,
            section_id=section_id,
            claim_id=claim_id,
        ))
    for index, failure in enumerate(binding_failures):
        issues.append(_issue(f"safety-binding-{index}", "epistemic_safety", "claim", "writer_binding_failed", failure))

    # Completeness contains the full research agenda, including verification
    # and author-review obligations.  Supported rows cannot be silently
    # filtered out merely because the Architect forgot to place their claims
    # in an argument graph: that is a plan failure, not a reason to report a
    # complete Method.  Non-supported review rows remain author-facing sidecar
    # work and do not force mechanical prose expansion.
    planned_claim_ids = {
        claim_id for unit in units.values() for claim_id in unit.claim_ids
    }
    # A partial row with no authorized claim is still a review/diagnostic
    # sidecar.  Treating it as a final-writing unit makes the plan gate fail
    # for obligations that have no repository-backed sentence to place in an
    # argument graph.  Partial rows with one or more authorized claims remain
    # required and must be planned just like fully supported rows.
    supported_rows = [item for item in completeness.items if _required_supported_row(item)]
    missing_graph_rows = [
        item for item in supported_rows
        if not set(item.claim_ids).intersection(planned_claim_ids)
    ]
    for item in missing_graph_rows:
        issues.append(_issue(
            f"supported-plan:{item.obligation_id}",
            "publication_utility",
            "stage",
            "supported_unit_missing_from_argument_graph",
            "A supported reference unit is absent from the Method argument graph.",
            stage_id=item.obligation_id,
        ))
    used_claim_ids = {claim_id for output in outputs.values() for claim_id in output.used_claim_ids}
    # A declared ``used_claim_id`` is a proposal, not proof: the claim must be
    # rendered in the section that declares it.  Unrendered used claims fail
    # the supported-recall and the utility gate with a typed issue.
    rendered_used_claims: set[str] = set()
    unrendered_used_claims: list[tuple[str, str]] = []
    for output in outputs.values():
        for claim_id in output.used_claim_ids:
            claim = claims_by_id.get(claim_id)
            if claim is None or _claim_rendered_in(output.section_markdown, claim):
                rendered_used_claims.add(claim_id)
            else:
                unrendered_used_claims.append((output.section_id, claim_id))
    for section_id, claim_id in sorted(unrendered_used_claims):
        issues.append(_issue(
            f"unrendered-claim:{section_id}:{claim_id}",
            "publication_utility",
            "claim",
            "supported_claim_not_rendered",
            "A claim declared as used is not rendered by its bound section span.",
            section_id=section_id,
            claim_id=claim_id,
        ))
    covered_supported = sum(
        1 for item in supported_rows
        if item.claim_ids and set(item.claim_ids).intersection(rendered_used_claims)
    )
    supported_recall = _ratio(covered_supported, len(supported_rows))

    required_moves = [
        (section.section_id, move.move)
        for section in plan.sections for move in section.moves if move.required
    ]
    completed_moves = {
        (section_id, move)
        for section_id, output in outputs.items()
        for move in output.completed_rhetorical_moves
    }
    # Writer-declared moves are proposals, not proof.  Each required move must
    # be witnessed by an exact authored span that realizes bound claim tokens,
    # renders a bound equation/configuration, or carries the generic role
    # vocabulary.  The witness span is recorded per section so the coverage
    # matrix and the move/role gates bind content, not metadata.
    move_witnesses: dict[tuple[str, str], tuple[int, int, str]] = {}
    move_witness_issues: list[PublicationQualityIssueV1] = []
    bound_moves: set[tuple[str, str]] = set()
    for section in plan.sections:
        output = outputs.get(section.section_id)
        if output is None:
            continue
        used_claim_objects = {
            claim_id: claims_by_id[claim_id]
            for claim_id in output.used_claim_ids
            if claim_id in claims_by_id
        }
        used_equation_objects = {
            equation_id: equation_by_id[equation_id]
            for equation_id in output.used_equation_ids
            if equation_id in equation_by_id
        }
        used_configuration_objects = {
            configuration_id: config_by_id[configuration_id]
            for configuration_id in output.used_configuration_ids
            if configuration_id in config_by_id
        }
        for move in {item[1] for item in required_moves if item[0] == section.section_id}:
            witness = _move_witness_span(
                output.section_markdown,
                move,
                used_claims=used_claim_objects,
                used_equations=used_equation_objects,
                used_configurations=used_configuration_objects,
            )
            if witness is not None:
                bound_moves.add((section.section_id, move))
                move_witnesses[(section.section_id, move)] = witness
            elif (section.section_id, move) in completed_moves:
                move_witness_issues.append(_issue(
                    f"move-content:{section.section_id}:{move}",
                    "publication_utility",
                    "section",
                    "required_move_content_missing",
                    f"Required rhetorical move {move} was declared but no authored span realizes its bound content.",
                    section_id=section.section_id,
                ))
    bound_required_moves = [
        item for item in required_moves if item in bound_moves
    ]
    move_coverage = _ratio(len(bound_required_moves), len(required_moves))
    planned_moves = {
        (section.section_id, move.move)
        for section in plan.sections for move in section.moves
    }
    for section_id, move in required_moves:
        if (section_id, move) not in bound_moves:
            issues.append(_issue(
                f"move:{section_id}:{move}", "publication_utility", "section",
                "required_argument_move_missing", f"Required rhetorical move {move} was not proven by authored content.",
                section_id=section_id,
            ))
    issues.extend(move_witness_issues)

    required_equations = {item for unit in units.values() for item in unit.equation_ids}
    used_equations = {item for output in outputs.values() for item in output.used_equation_ids}
    required_configs = {item for unit in units.values() for item in unit.configuration_ids}
    used_configs = {item for output in outputs.values() for item in output.used_configuration_ids}
    numeric_configs = {
        item.configuration_id for item in (configurations.claims if configurations else ())
        if isinstance(item.value, (int, float)) and not isinstance(item.value, bool)
    }
    rendered_equations = {
        equation_id for equation_id in (used_equations & required_equations)
        if equation_id in equation_by_id
        and _equation_rendered(final_text, equation_by_id[equation_id])
    }
    rendered_configs = {
        config_id for config_id in (used_configs & required_configs)
        if config_id in config_by_id and _configuration_rendered(final_text, config_by_id[config_id])
    }
    rendered_numeric_configs = rendered_configs & numeric_configs
    role_moves = {
        "overview": {"mechanism_overview"},
        "representation": {"formal_objects_and_notation"},
        "transformation": {"algorithm_or_data_flow", "implementation_realization"},
        "branch": {"configuration_and_branches"},
        "equation": {"equation_or_derivation"},
        "objective": {"design_objective", "training_objective"},
        "output": {"inference_and_output"},
    }
    # A content role is *required* only when the plan demands one of its moves
    # as required or the argument graph carries the role's content (equations
    # for the equation role, configurations for the branch role, claims for
    # transformation/overview).  A merely planned non-required move name must
    # not turn a role into "missing": the writer's content obligations come
    # from required moves and the closed content sets, not from optional move
    # vocabulary.  Coverage additionally requires the role's content to be
    # rendered where it is required.
    unit_content_roles: dict[str, set[str]] = {}
    for unit in units.values():
        role_marks: set[str] = set()
        if unit.equation_ids:
            role_marks.update({"equation", "representation"})
        if unit.configuration_ids:
            role_marks.update({"branch", "representation"})
        if unit.claim_ids:
            role_marks.update({"transformation", "overview"})
        unit_content_roles[unit.argument_unit_id] = role_marks
    required_move_set = set(required_moves)
    content_role_status: dict[str, Literal["covered", "missing", "not_required"]] = {}
    for role, moves in role_moves.items():
        planned_role_moves = {
            item for item in planned_moves if item[1] in moves
        }
        required_role_moves = {
            item for item in required_move_set if item[1] in moves
        }
        content_required = any(
            role in unit_content_roles.get(unit_id, set())
            for section in plan.sections
            for unit_id in section.argument_unit_ids
        )
        if not required_role_moves and not content_required:
            content_role_status[role] = "not_required"
            continue
        content_covered = True
        if role == "equation":
            content_covered = _ratio(len(rendered_equations), len(required_equations)) == 1.0
        elif role == "branch":
            content_covered = _ratio(len(rendered_configs), len(required_configs)) == 1.0
        elif role == "representation":
            content_covered = _ratio(len(rendered_equations), len(required_equations)) == 1.0 and (
                _ratio(len(rendered_configs), len(required_configs)) == 1.0
            )
        elif role in {"transformation", "overview"}:
            content_covered = not unrendered_used_claims
        if required_role_moves and not all(
            item in bound_moves for item in required_role_moves
        ):
            content_role_status[role] = "missing"
        elif not content_covered:
            content_role_status[role] = "missing"
        else:
            content_role_status[role] = "covered"
    accepted_sections = set(outputs)
    stage_coverage = _ratio(
        sum(1 for section in plan.sections if section.section_id in accepted_sections),
        len(plan.sections),
    )
    coherent_sections = sum(
        1
        for section in plan.sections
        if section.section_id in accepted_sections
        and set(section.dependencies).issubset(accepted_sections)
    )
    coherence_score = _ratio(coherent_sections, len(plan.sections))
    if coherence_score < 1.0:
        issues.append(_issue(
            "coherence",
            "publication_utility",
            "document",
            "section_dependency_incomplete",
            "A section is missing an accepted dependency or authored section.",
        ))
    reproducibility_moves = {
        "algorithm_or_data_flow", "implementation_realization",
        "configuration_and_branches", "inference_and_output",
    }
    required_repro = {
        (section.section_id, move.move)
        for section in plan.sections for move in section.moves
        if move.required and move.move in reproducibility_moves
    }
    reproducibility = _ratio(
        sum(1 for item in required_repro if item in bound_moves),
        len(required_repro),
    )
    section_texts = [output.section_markdown for output in outputs.values()]
    duplicate_rate, duplicate_issue_messages = _duplicate_rate(
        section_texts,
        used_claims={
            claim_id: claims_by_id[claim_id]
            for claim_id in used_claim_ids
            if claim_id in claims_by_id
        },
    )
    if duplicate_rate > 0:
        issues.append(_issue(
            "duplicate-information",
            "publication_utility",
            "document",
            "duplicate_information",
            "The final Method repeats or paraphrases the same information: "
            + "; ".join(duplicate_issue_messages[:4]),
        ))
    closed_ids = set()
    closed_ids.update(str(section.section_id) for section in plan.sections)
    closed_ids.update(str(unit.argument_unit_id) for unit in plan.argument_units)
    closed_ids.update(str(item.claim_id) for item in (getattr(claims, "claims", ()) or ()))
    closed_ids.update(str(item.equation_id) for item in (equations.equations if equations else ()))
    closed_ids.update(str(item.configuration_id) for item in (configurations.claims if configurations else ()))
    closed_ids.update(str(item.obligation_id) for item in completeness.items)
    closed_ids.discard("")
    lower_text = final_text.lower()
    leaked_ids = sorted(
        identifier for identifier in closed_ids
        if identifier.lower() in lower_text
    )
    internal_tokens = sorted(set(re.findall(
        r"\b(?:span|fact|claim|obl|evidence|validator|gap|sym)[-:][A-Za-z0-9_:.-]+\b",
        final_text,
        flags=re.IGNORECASE,
    )))
    internal_tokens.extend(leaked_ids)
    internal_tokens = sorted(dict.fromkeys(internal_tokens))
    terminology_ok = not internal_tokens
    if internal_tokens:
        issues.append(_issue("internal-bookkeeping", "publication_utility", "sentence", "internal_bookkeeping_exposed", ", ".join(internal_tokens[:8])))
    # Code-trace prose guard (W/C.3): a section that serializes raw code
    # identifiers as sentence subjects is not Method language even when every
    # sentence validates.  This is a publication-utility issue that routes to
    # Rewrite; it never weakens evidence gates.
    code_trace_sections = find_code_trace_prose_sections(
        list(outputs.values()), fallback_text=final_text
    )
    for section_id, _section_text in code_trace_sections:
        issues.append(_issue(
            f"code-trace:{section_id or 'document'}",
            "publication_utility",
            "section",
            "code_trace_prose_not_method_language",
            "The section reads like a source-code execution log: raw code "
            "identifiers dominate the prose instead of Method language. Rewrite "
            "it from the reader's perspective while preserving the supported "
            "meaning, qualifiers, and numeric/formula values.",
            section_id=section_id,
        ))
    required_qualifiers = {
        (claim_id, str(qualifier).strip())
        for claim_id in used_claim_ids
        for qualifier in getattr(claims_by_id.get(claim_id), "required_qualifiers", ())
        if str(qualifier).strip()
    }
    preserved_qualifiers = {
        item for item in required_qualifiers if _phrase_present(final_text, item[1])
    }
    qualifier_coverage = _ratio(len(preserved_qualifiers), len(required_qualifiers))
    for claim_id, qualifier in sorted(required_qualifiers - preserved_qualifiers):
        issue_digest = hashlib.sha256(qualifier.encode("utf-8")).hexdigest()[:12]
        issues.append(_issue(
            f"qualifier:{claim_id}:{issue_digest}",
            "publication_utility",
            "claim",
            "required_qualifier_missing",
            f"Required qualifier is not preserved: {qualifier}",
            claim_id=claim_id,
        ))
    # Diagnostic only: measure distinct authorized claim vocabulary in the
    # authored body.  This is not a word-count target and is never used to
    # reward empty expansion.
    body_words = re.findall(
        r"[A-Za-z0-9_]+",
        "\n".join(
            line for line in final_text.splitlines()
            if not line.lstrip().startswith("#")
        ).lower(),
    )
    claim_words = {
        token
        for claim_id in used_claim_ids
        for token in re.findall(
            r"[A-Za-z0-9_]+",
            str(getattr(claims_by_id.get(claim_id), "canonical_text", "") or "").lower(),
        )
        if len(token) > 2
    }
    information_density = (
        _ratio(len(set(body_words).intersection(claim_words)), len(set(body_words)))
        if body_words else 0.0
    )
    editable_sections = sum(
        1 for output in outputs.values()
        if _section_editable(output.section_markdown)
    )
    editable_rate = _ratio(editable_sections, len(plan.sections))
    if editable_rate < 1.0:
        for output in outputs.values():
            if not _section_editable(output.section_markdown):
                issues.append(_issue(
                    f"editable:{output.section_id}",
                    "publication_utility",
                    "section",
                    "section_not_editable",
                    "The section has no content-bearing editable body.",
                    section_id=output.section_id,
                ))
    audit_sentences = [
        (output.section_id, sentence)
        for output in outputs.values()
        for sentence in _code_audit_sentences(output.section_markdown)
    ]
    for section_id, sentence in audit_sentences[:8]:
        issues.append(_issue(
            f"audit:{section_id}:{hashlib.sha256(sentence.encode('utf-8')).hexdigest()[:10]}",
            "publication_utility",
            "section",
            "code_audit_list",
            "A sentence reads as a bare code-fact inventory line, not Method prose.",
            section_id=section_id,
        ))
    mismatch_rows = [item for item in completeness.items if item.status == "paper_code_mismatch"]
    mismatch_preserved = all(item.reason.strip() and item.next_action.strip() for item in mismatch_rows)
    if not mismatch_preserved:
        issues.append(_issue("mismatch-lost", "publication_utility", "document", "paper_code_mismatch_not_actionable", "A paper/code mismatch lacks an author-facing reason or next action."))
    for request in open_research_requests:
        request_id = str(getattr(request, "request_id", "") or "unknown")
        section_id = str(getattr(request, "section_id", "") or "")
        issues.append(_issue(
            f"research-request:{request_id}", "publication_utility", "section",
            "writing_research_request_open", "A Writer-requested authority artifact is still unresolved.",
            section_id=section_id,
        ))
    for index, failure in enumerate(utility_failures):
        issues.append(_issue(
            f"utility-failure:{index}", "publication_utility", "document",
            "publication_utility_failure", failure,
        ))

    unresolved_supported = [
        item.obligation_id for item in supported_rows
        if not item.claim_ids or not set(item.claim_ids).intersection(used_claim_ids)
    ]
    for obligation_id in unresolved_supported:
        issues.append(_issue(
            f"supported-unit:{obligation_id}", "publication_utility", "stage",
            "supported_unit_missing_from_final", "A supported reference unit was not bound into final text.",
            stage_id=obligation_id,
        ))
    known_unit_ids = set(units)
    graph_refs_valid = all(
        set(section.argument_unit_ids).issubset(known_unit_ids)
        and bool(section.argument_unit_ids)
        for section in plan.sections
    )
    supported_graph_complete = not missing_graph_rows
    semantic_frame_surface_present = any(
        unit.semantic_frame is not None for unit in plan.argument_units
    )
    unresolved_frame_relations = [
        (unit.argument_unit_id, relation_id)
        for unit in plan.argument_units
        if unit.semantic_frame is not None
        for relation_id in unit.semantic_frame.unresolved_relation_ids
    ]
    for unit_id, relation_id in unresolved_frame_relations[:12]:
        issues.append(_issue(
            f"plan-unresolved-relation:{unit_id}:{relation_id}",
            "publication_utility",
            "stage",
            "semantic_relation_unresolved",
            "A semantic relation lacks an exact acyclic endpoint binding.",
            stage_id=unit_id,
        ))
    semantic_frame_gate = not (
        semantic_frame_surface_present and unresolved_frame_relations
    )
    critical_high_ids = {
        item.obligation_id for item in completeness.items
        if item.importance in {"critical", "high"}
    }
    assignment_ids = {
        item.obligation_id for item in plan.obligation_assignments
    }
    assignment_surface_present = bool(plan.obligation_assignments)
    missing_assignments = (
        critical_high_ids - assignment_ids if assignment_surface_present else set()
    )
    unknown_assignments = (
        assignment_ids - critical_high_ids if assignment_surface_present else set()
    )
    unplaced_assignments = [
        item for item in plan.obligation_assignments
        if item.importance in {"critical", "high"}
        and item.placement_state == "unplaced"
    ]
    if missing_assignments:
        issues.append(_issue(
            "plan-missing-obligation-assignments",
            "publication_utility",
            "document",
            "critical_high_assignment_missing",
            "Critical/high obligations are absent from the typed plan: "
            + ",".join(sorted(missing_assignments)),
        ))
    if unknown_assignments:
        issues.append(_issue(
            "plan-unknown-obligation-assignments",
            "publication_utility",
            "document",
            "unknown_obligation_assignment",
            "The typed plan contains assignments outside the critical/high completeness set: "
            + ",".join(sorted(unknown_assignments)),
        ))
    for assignment in unplaced_assignments[:12]:
        issues.append(_issue(
            f"plan-unplaced:{assignment.obligation_id}",
            "publication_utility",
            "stage",
            "critical_high_obligation_unplaced",
            "A critical/high obligation remains typed but unplaced; the plan cannot pass.",
            stage_id=assignment.obligation_id,
        ))
    assignment_gate = not (
        missing_assignments or unknown_assignments or unplaced_assignments
    )
    # Candidate planning is governed by reader-facing graph coverage.  Exact
    # assignment and semantic-frame closure remain visible as audit issues but
    # no longer block a useful candidate or its verified sentence split.
    plan_gate = all((
        bool(plan.sections and plan.argument_units),
        graph_refs_valid,
        supported_graph_complete,
    ))
    if not plan_gate:
        issues.append(_issue(
            "plan-empty",
            "publication_utility",
            "document",
            "argument_plan_incomplete",
            "Every core section requires valid argument-unit references and every supported unit must be planned.",
        ))
    utility_gate = all((
        supported_recall == 1.0,
        move_coverage == 1.0,
        stage_coverage == 1.0,
        coherence_score == 1.0,
        reproducibility == 1.0,
        qualifier_coverage == 1.0,
        duplicate_rate == 0.0,
        terminology_ok,
        not audit_sentences,
        not code_trace_sections,
        editable_rate == 1.0,
        mismatch_preserved,
        not open_research_requests,
        not utility_failures,
        not unrendered_used_claims,
        all(status != "missing" for status in content_role_status.values()),
        _ratio(len(rendered_equations), len(required_equations)) == 1.0,
        _ratio(len(rendered_configs), len(required_configs)) == 1.0,
    ))
    utility = PublicationUtilityMetricsV1(
        supported_unit_recall=supported_recall,
        completeness_coverage=supported_recall,
        argument_move_coverage=move_coverage,
        equation_coverage=_ratio(len(rendered_equations), len(required_equations)),
        configuration_coverage=_ratio(len(rendered_configs), len(required_configs)),
        numeric_coverage=_ratio(len(rendered_numeric_configs), len(numeric_configs)),
        reproducibility_detail_coverage=reproducibility,
        coherence_score=coherence_score,
        qualifier_coverage=qualifier_coverage,
        information_density=information_density,
        stage_coverage=stage_coverage,
        duplicate_information_rate=duplicate_rate,
        terminology_notation_consistent=terminology_ok,
        editable_section_rate=editable_rate,
        paper_code_mismatch_preserved=mismatch_preserved,
        content_role_status=content_role_status,
        utility_gate_passed=utility_gate,
    )
    final_gate = safety.hard_gate_passed and plan_gate and utility_gate
    intrinsic_safety_failure = bool(
        not ledger.hard_gate_passed
        or binding_failures
        or unsupported_positive_claims != 0
        or not source_integrity
        or final_text_validation_status == "failed"
    )
    status: Literal["publication_ready", "incomplete", "blocked"] = (
        "blocked" if intrinsic_safety_failure
        else "publication_ready" if final_gate
        else "incomplete"
    )
    coverage_matrix = _build_coverage_matrix(
        completeness=completeness,
        plan=plan,
        outputs=outputs,
        ledger=ledger,
    )
    return PublicationQualityReportV1(
        status=status,
        plan_gate_passed=plan_gate,
        final_integrity_gate_passed=final_gate,
        safety=safety,
        utility=utility,
        coverage_matrix=coverage_matrix,
        issues=tuple(issues),
    )


def _ratio(numerator: int, denominator: int) -> float:
    return 1.0 if denominator == 0 else round(numerator / denominator, 6)


_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "is", "are", "was",
    "were", "be", "been", "being", "it", "its", "this", "that", "these", "those",
    "for", "with", "as", "by", "at", "from", "into", "over", "under", "between",
    "which", "who", "whom", "whose", "their", "there", "they", "them", "then",
    "than", "such", "so", "not", "no", "nor", "also", "but", "if", "when", "while",
    "will", "would", "can", "could", "may", "might", "must", "shall", "should",
    "does", "do", "did", "has", "have", "had", "itself", "himself", "herself",
    "each", "every", "either", "neither", "both", "all", "any", "some", "most",
    "more", "less", "few", "many", "one", "two", "first", "second", "last", "next",
    "use", "uses", "used", "using", "show", "shows", "shown", "via", "per", "etc",
})


def _content_tokens(text: str) -> list[str]:
    return [
        token for token in re.findall(r"[a-z][a-z0-9_]*", text.lower())
        if token not in _STOPWORDS
    ]


def _sentence_spans(text: str) -> list[tuple[int, int, str]]:
    """Split section text without breaking dotted repository bindings.

    Parenthetical identifiers such as ``GaussianModel.capture`` and
    ``self._features_dc`` are valid binding annotations.  Treating their dots
    as sentence boundaries detached the subject/predicate/operand anchors and
    made rendered supported claims appear missing.
    """

    spans: list[tuple[int, int, str]] = []
    start = 0
    index = 0
    while index < len(text):
        char = text[index]
        boundary_end = -1
        if char == "\n":
            boundary_end = index
        elif char in ".!?":
            if (
                char == "."
                and index > 0
                and index + 1 < len(text)
                and (text[index - 1].isalnum() or text[index - 1] == "_")
                and (text[index + 1].isalnum() or text[index + 1] == "_")
            ):
                index += 1
                continue
            boundary_end = index + 1
        if boundary_end < 0:
            index += 1
            continue
        raw = text[start:boundary_end]
        sentence = raw.strip()
        if sentence and not sentence.lstrip().startswith("#"):
            local_start = start + len(raw) - len(raw.lstrip())
            spans.append((local_start, local_start + len(sentence), sentence))
        start = index + 1
        while start < len(text) and text[start].isspace() and text[start] != "\n":
            start += 1
        index = start
    raw = text[start:]
    sentence = raw.strip()
    if sentence and not sentence.lstrip().startswith("#"):
        local_start = start + len(raw) - len(raw.lstrip())
        spans.append((local_start, local_start + len(sentence), sentence))
    return spans


def _claim_rendered_in(text: str, claim: Any) -> bool:
    """Whether a sentence realizes a claim's canonical semantic anchors.

    The old Jaccard test divided by every word in the generated sentence.  A
    perfectly valid academic sentence that embedded a short code claim in an
    explanation therefore looked *less* rendered as the explanation became
    clearer.  Rendering is directional: the sentence must retain most of the
    claim's content anchors, while it may add reader-facing context.  A small
    precision floor still prevents a long unrelated paragraph from matching a
    claim through one generic token.
    """
    claim_tokens = _content_tokens(str(getattr(claim, "canonical_text", "") or ""))
    if not claim_tokens:
        return False
    claim_set = set(claim_tokens)
    for _start, _end, sentence in _sentence_spans(text):
        sentence_tokens = _content_tokens(sentence)
        if not sentence_tokens:
            continue
        sentence_set = set(sentence_tokens)
        overlap = len(claim_set & sentence_set)
        anchor_recall = overlap / max(1, len(claim_set))
        sentence_precision = overlap / max(1, len(sentence_set))
        if anchor_recall >= 0.75 and (
            sentence_precision >= 0.16 or overlap >= min(3, len(claim_set))
        ):
            return True
    return False


_EQUATION_RENDER_IDENTIFIER_MIN = 0.5
_OUTPUT_VOCABULARY = frozenset({
    "return", "output", "emit", "produce", "yield", "result", "prediction",
    "predict", "render", "readout", "response", "generated", "writes", "report",
})
_CONDITIONAL_VOCABULARY = frozenset({
    "when", "if", "unless", "else", "elif", "branch", "case", "depending",
    "condition", "conditional", "variant", "mode", "path",
})
_BOUNDARY_VOCABULARY = frozenset({
    "when", "if", "unless", "only", "until", "boundary", "limit", "complexity",
    "cost", "memory", "budget", "worst", "best",
})
_LIMITATION_VOCABULARY = frozenset({
    "limitation", "mismatch", "cannot", "unverified", "caveat", "outside",
    "absent", "unsupported", "review", "explicitly", "does_not",
})
_CONFIG_IGNORED_VALUE_TOKENS = frozenset({
    "self", "cfg", "config", "use", "set", "true", "false", "none", "null",
    "nullptr", "list", "str", "int", "float", "bool",
})
_ORG_ONLY_MOVES = frozenset({
    "problem_or_local_context", "design_objective",
    "intuition_or_rationale", "transition_to_next_section",
})
# Process/sequence vocabulary distinguishes a data-flow or implementation
# sentence from a bare fact inventory line ("X calls Y, Z.").  A claim-shaped
# inventory sentence without any flow marker cannot witness algorithm/data-flow
# or implementation moves, so readable code-audit lists fail the move gates
# even when they carry no internal ids.
_FLOW_VOCABULARY = frozenset({
    "then", "after", "before", "first", "next", "once", "while", "during",
    "subsequently", "finally", "eventually", "via", "through", "by", "step",
    "phase", "stage", "process", "pipeline", "loop", "iterate", "iterates",
    "sequence", "order", "followed", "follows", "inputs", "outputs",
})
# Behavior-predicate inventory pattern: a sentence that merely serializes a
# code fact record ("<symbol> calls <x>, <y>", "<symbol> loads weights <w>",
# "<symbol> computes formula <n>, <k>") is a code-audit line, not Method prose.
# The subject must be a code symbol (dotted / underscored / ``sym:`` path) and
# leading connective wrappers and markdown backticks are normalized away so
# wrapped records ("the method first <symbol> calls ...", "the `symbol`
# method calls ...") cannot game the detector.
_AUDIT_PREDICATE_PATTERN = re.compile(
    r"^\s*(?:the\s+)?"
    r"(?:`?[A-Za-z_][\w.:]*[_.:][\w.:]*`?|`?sym:[\w.:]+`?)"
    r"(?:\s+(?:operation|method|function|entrypoint|component|procedure|stage|step|phase))?"
    r"(?:\s+(?:loads weights|loads the weights|computes formula|computes the formula|"
    r"computes|returns|concatenates|normalizes|branches on|sorts by|selects top k|"
    r"calls|propagates|attends|reduces|writes|stores|reads|constructs|invokes|runs|applies|"
    r"loads|stores|reads))"
    r"\b",
    flags=re.IGNORECASE,
)


def _configuration_rendered(text: str, configuration: Any) -> bool:
    """Require the config key's final dotted segment and its value tokens.

    A declared-but-unrendered configuration is a binding failure: mentioning
    only the key (or only a generic value) is not a rendering of the
    configuration claim.  Generic value scaffolding tokens (``self.cfg`` and
    similar) are ignored because they are projection mechanics, not content.
    """

    text_tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
    key = str(configuration.key or "").lower()
    key_segment = key.rsplit(".", 1)[-1].rsplit(":", 1)[-1]
    key_tokens = [token for token in re.findall(r"[a-z0-9]+", key_segment) if token]
    value = getattr(configuration, "value", None)
    value_tokens = [
        token for token in re.findall(r"[a-z0-9]+", str(value).lower())
        if token not in _CONFIG_IGNORED_VALUE_TOKENS
    ]
    if not key_tokens:
        return False
    if not value_tokens:
        return bool(set(key_tokens) <= text_tokens)
    return bool(set(key_tokens) <= text_tokens) and bool(set(value_tokens) <= text_tokens)


def _move_witness_span(
    section_text: str,
    move: str,
    *,
    used_claims: dict[str, Any],
    used_equations: dict[str, Any],
    used_configurations: dict[str, Any],
) -> tuple[int, int, str] | None:
    """Find the first sentence that deterministically witnesses a move.

    A move is proven only by authored content: a sentence realizing a bound
    claim's canonical tokens, rendering a bound equation/configuration, or
    carrying the generic role vocabulary.  The witness span is recorded so
    the quality report binds each completed move to exact final-text bytes;
    missing or ambiguous content fails closed.
    """

    for start, end, sentence in _sentence_spans(section_text):
        if move == "equation_or_derivation":
            if any(_equation_rendered(sentence, equation) for equation in used_equations.values()):
                return start, end, sentence
            continue
        if move == "formal_objects_and_notation":
            if _notation_rendered(sentence, used_equations, used_configurations):
                return start, end, sentence
            continue
        if move == "configuration_and_branches":
            if any(_configuration_rendered(sentence, config) for config in used_configurations.values()):
                return start, end, sentence
            if _has_vocabulary(sentence, _CONDITIONAL_VOCABULARY) and (
                any(_configuration_rendered(sentence, config) for config in used_configurations.values())
                or _realizes_any_claim(sentence, used_claims)
            ):
                return start, end, sentence
            continue
        if move == "inference_and_output":
            if _has_vocabulary(sentence, _OUTPUT_VOCABULARY) and _realizes_any_claim(sentence, used_claims):
                return start, end, sentence
            continue
        if move == "complexity_or_boundary_conditions":
            if _has_vocabulary(sentence, _BOUNDARY_VOCABULARY) and (
                _realizes_any_claim(sentence, used_claims)
                or len(_content_tokens(sentence)) >= 4
            ):
                return start, end, sentence
            continue
        if move == "limitations_or_mismatch":
            if _has_vocabulary(sentence, _LIMITATION_VOCABULARY) and len(_content_tokens(sentence)) >= 4:
                return start, end, sentence
            continue
        if move in _ORG_ONLY_MOVES:
            content = _content_tokens(sentence)
            if len(content) >= 8 or (
                _has_vocabulary(sentence, _FLOW_VOCABULARY) and len(content) >= 4
            ):
                return start, end, sentence
            continue
        if move in {"algorithm_or_data_flow", "implementation_realization"}:
            if any(_equation_rendered(sentence, equation) for equation in used_equations.values()):
                return start, end, sentence
            if _realizes_any_claim(sentence, used_claims) and _has_vocabulary(
                sentence, _FLOW_VOCABULARY
            ):
                return start, end, sentence
            continue
        # mechanism_overview
        if _realizes_any_claim(sentence, used_claims) or any(
            _equation_rendered(sentence, equation) for equation in used_equations.values()
        ):
            return start, end, sentence
    return None


def _normalize_audit_prefixes(text: str) -> str:
    """Strip backticks and leading flow wrappers before the audit shape test."""

    candidate = re.sub(r"`", "", text)
    candidate = re.sub(
        r"^\s*(?:and\s+)?(?:the\s+)?(?:method|system|pipeline)\s+"
        r"(?:first|then|finally|subsequently|afterwards)\s+",
        "",
        candidate,
        flags=re.IGNORECASE,
    )
    candidate = re.sub(
        r"^\s*(?:and\s+)?(?:finally|then|first|subsequently|afterwards)\s+(?:it\s+)?",
        "",
        candidate,
        flags=re.IGNORECASE,
    )
    candidate = re.sub(
        r"^\s*(?:and\s+)?(?:it\s+)?(?:first|then|finally|subsequently|afterwards)\s+",
        "",
        candidate,
        flags=re.IGNORECASE,
    )
    return candidate


def _code_audit_sentences(section_text: str) -> list[str]:
    """Sentences that read as bare code-fact inventory lines.

    The inventory shape is the generic behavior-predicate serialization
    (``<symbol> calls <operand>, <operand>``).  It fails closed even when the
    text contains no internal ids or ``sym:`` refs, and wrapper prefixes such
    as ``the method first`` or backticked symbols are normalized away.
    """

    normalized = _normalize_audit_prefixes(section_text)
    return [
        sentence
        for _start, _end, sentence in _sentence_spans(normalized)
        if _AUDIT_PREDICATE_PATTERN.match(sentence.strip())
    ]


def _realizes_any_claim(sentence: str, used_claims: dict[str, Any]) -> bool:
    sentence_tokens = set(_content_tokens(sentence))
    if not sentence_tokens:
        return False
    for claim in used_claims.values():
        claim_tokens = set(_content_tokens(str(getattr(claim, "canonical_text", "") or "")))
        if not claim_tokens:
            continue
        overlap = len(claim_tokens & sentence_tokens)
        union = len(claim_tokens | sentence_tokens)
        if union and overlap / union >= 0.5:
            return True
    return False


def _notation_rendered(
    sentence: str,
    used_equations: dict[str, Any],
    used_configurations: dict[str, Any],
) -> bool:
    """Formal notation vocabulary comes only from bound closed IDs."""
    sentence_tokens = set(re.findall(r"[a-z0-9_]+", sentence.lower()))
    for equation in used_equations.values():
        identifiers = set(re.findall(r"[a-z][a-z0-9_]*", str(equation.expression).lower()))
        if identifiers & sentence_tokens:
            return True
    for configuration in used_configurations.values():
        key_tokens = set(re.findall(
            r"[a-z0-9_]+", str(configuration.key).lower().rsplit(".", 1)[-1]
        ))
        if key_tokens & sentence_tokens:
            return True
    return False


def _has_vocabulary(sentence: str, vocabulary: frozenset[str]) -> bool:
    tokens = set(re.findall(r"[a-z0-9_]+", sentence.lower()))
    return bool(vocabulary & tokens)


def _phrase_present(text: str, phrase: str) -> bool:
    """Match a qualifier by normalized lexical tokens, not raw punctuation."""

    phrase_tokens = re.findall(r"[a-z0-9_]+", phrase.lower())
    text_tokens = re.findall(r"[a-z0-9_]+", text.lower())
    if not phrase_tokens:
        return True
    width = len(phrase_tokens)
    if any(
        text_tokens[index:index + width] == phrase_tokens
        for index in range(max(0, len(text_tokens) - width + 1))
    ):
        return True
    # Code conditions are often rendered as equivalent paper prose, e.g.
    # ``knn_method in ['ivf', 'brute_force']`` becomes "when knn_method is
    # either 'ivf' or 'brute_force'".  Permit that narrow paraphrase only when
    # every identifier/value token from the authorized qualifier remains and
    # an explicit conditional marker is present; do not turn this into a
    # generic subset or semantic-similarity check.
    if " in " in f" {phrase.lower()} ":
        required_tokens = set(phrase_tokens) - {"in"}
        condition_markers = {"in", "when", "if", "under", "either", "where", "case"}
        return required_tokens.issubset(set(text_tokens)) and bool(
            condition_markers.intersection(text_tokens)
        )
    return False


def _build_coverage_matrix(
    *,
    completeness: MethodCompletenessMatrixV1,
    plan: MethodSectionPlanV2,
    outputs: dict[str, PublicationMethodSectionOutputV1],
    ledger: FinalTextAuthorshipLedgerV1,
) -> tuple[dict[str, Any], ...]:
    """Join agenda rows, planned argument units, used claims, and final spans.

    This is deliberately a diagnostic matrix: it does not authorize new
    prose.  It makes omissions visible at the same obligation granularity as
    the completeness matrix and lets an author distinguish a supported unit
    missing from the graph from a unit planned but not rendered.
    """

    units_by_id = {item.argument_unit_id: item for item in plan.argument_units}
    sections_by_unit: dict[str, set[str]] = {}
    for section in plan.sections:
        for unit_id in section.argument_unit_ids:
            sections_by_unit.setdefault(unit_id, set()).add(section.section_id)
    used_claims_by_section = {
        section_id: set(output.used_claim_ids)
        for section_id, output in outputs.items()
    }
    rows: list[dict[str, Any]] = []
    for item in completeness.items:
        claim_ids = tuple(dict.fromkeys(item.claim_ids))
        planned_units = tuple(
            unit.argument_unit_id
            for unit in units_by_id.values()
            if set(unit.claim_ids).intersection(claim_ids)
        )
        planned_sections = tuple(sorted({
            section_id
            for unit_id in planned_units
            for section_id in sections_by_unit.get(unit_id, set())
        }))
        used_claim_ids = tuple(sorted({
            claim_id
            for claim_ids_in_section in used_claims_by_section.values()
            for claim_id in claim_ids_in_section.intersection(claim_ids)
        }))
        final_span_ids = tuple(sorted(
            span.final_span_id
            for span in ledger.spans
            if span.section_id in set(planned_sections)
        ))
        required_in_final = _required_supported_row(item)
        if not required_in_final:
            coverage_status = "sidecar"
        elif not planned_units:
            coverage_status = "missing_from_argument_graph"
        elif not used_claim_ids or not final_span_ids:
            coverage_status = "planned_but_not_rendered"
        else:
            coverage_status = "covered"
        rows.append({
            "obligation_id": item.obligation_id,
            "agenda_status": item.status,
            "authority_lane": item.authority_lane,
            "claim_ids": list(claim_ids),
            "planned_argument_unit_ids": list(planned_units),
            "planned_section_ids": list(planned_sections),
            "used_claim_ids": list(used_claim_ids),
            "final_span_ids": list(final_span_ids),
            "required_in_final": required_in_final,
            "coverage_status": coverage_status,
        })
    return tuple(rows)


def _required_supported_row(item: Any) -> bool:
    """Whether a completeness row has authorized material for final prose."""

    status = str(getattr(item, "status", ""))
    claim_ids = tuple(getattr(item, "claim_ids", ()) or ())
    return status == "supported_by_repository" or (
        status == "partially_supported_by_repository" and bool(claim_ids)
    )


def _duplicate_rate(
    section_texts: list[str] | tuple[str, ...],
    *,
    used_claims: dict[str, Any] | None = None,
) -> tuple[float, list[str]]:
    """Exact, semantic, and claim-anchor duplicate detection.

    Each sentence is classified as duplicate at most once (the union of the
    three rules), so the rate is a proper fraction of duplicate sentences.
    Exact duplicates use normalized sentence text; semantic duplicates use a
    content-token Jaccard over first occurrences; a used claim whose canonical
    tokens are realized by more than one sentence is duplicate information even
    when the surface text differs.
    """

    sentences: list[tuple[str, str, str]] = []
    for section_index, text in enumerate(section_texts):
        for _start, _end, sentence in _sentence_spans(text):
            normalized = " ".join(re.findall(r"[a-z0-9]+", sentence.lower()))
            if normalized:
                sentences.append((normalized, f"section-{section_index}", sentence))
    messages: list[str] = []
    duplicate_indexes: set[int] = set()
    seen_normalized: set[str] = set()
    seen_content: list[set[str]] = []
    seen_claim_sentences: dict[str, int] = {}
    for index, (normalized, _section, sentence) in enumerate(sentences):
        duplicate = False
        if normalized in seen_normalized:
            duplicate = True
        else:
            seen_normalized.add(normalized)
            tokens = list(dict.fromkeys(_content_tokens(normalized)))
            if len(tokens) >= 4:
                token_set = set(tokens)
                if any(
                    (token_set | anchor)
                    and len(token_set & anchor) / len(token_set | anchor) >= 0.7
                    for anchor in seen_content
                ):
                    duplicate = True
                    messages.append("semantic same-information sentence")
                else:
                    seen_content.append(token_set)
        if used_claims:
            for claim_id, claim in used_claims.items():
                if _claim_rendered_in(sentence, claim):
                    if claim_id in seen_claim_sentences:
                        duplicate = True
                    else:
                        seen_claim_sentences[claim_id] = index
        if duplicate:
            duplicate_indexes.add(index)
    for normalized, count in Counter(item[0] for item in sentences).items():
        if count > 1:
            messages.append(f"exact sentence repeated {count}x")
    for claim_id, first_index in sorted(seen_claim_sentences.items()):
        later = sum(
            1 for index, (_n, _s, sentence) in enumerate(sentences)
            if index > first_index and _claim_rendered_in(sentence, used_claims[claim_id])
        )
        if later:
            messages.append(f"claim {claim_id} realized in more than one sentence")
    total = len(sentences)
    rate = _ratio(len(duplicate_indexes), total) if total else 0.0
    return rate, list(dict.fromkeys(messages))


def _section_editable(text: str) -> bool:
    body = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#")).strip()
    if not body:
        return False
    if re.search(r"\b(?:TODO|TBD|placeholder|validator error)\b", body, flags=re.IGNORECASE):
        return False
    if body[-1] not in ".!?)]}":
        return False
    content = _content_tokens(body)
    if len(content) < 4 or len(set(content)) < 2:
        return False
    return True


def _equation_rendered(text: str, equation: Any) -> bool:
    """Check whether an authorized equation is rendered in the final text.

    Authorized equations may carry synthetic placeholder symbols (``x``/``y``)
    bound to real fact operands via ``symbol_bindings``.  The render check
    must substitute those bindings so it looks for the real operand names the
    Writer is expected to render, not the placeholder symbols.  When no
    bindings are supplied the expression is used verbatim (e.g. an equation
    whose expression already names its symbols).
    """

    expression = equation.expression
    bindings = getattr(equation, "symbol_bindings", None) or ()
    if bindings:
        concrete = expression
        # Replace longest symbol names first so a short symbol (``x``) cannot
        # corrupt a longer one (``x1``).  Word boundaries keep the substitution
        # token-accurate.
        for binding in sorted(bindings, key=lambda b: len(b.symbol), reverse=True):
            concrete = re.sub(
                r"(?<![A-Za-z0-9_])" + re.escape(binding.symbol) + r"(?![A-Za-z0-9_])",
                binding.operand_value,
                concrete,
            )
        expression = concrete
    identifiers = set(re.findall(r"[a-z][a-z0-9_]*", expression.lower()))
    text_tokens = set(re.findall(r"[a-z][a-z0-9_]*", text.lower()))
    numbers = set(re.findall(r"\d+(?:\.\d+)?", expression))
    operators = set(re.findall(r"[=+*/^-]", expression))
    identifier_ok = not identifiers or len(identifiers & text_tokens) / len(identifiers) >= 0.5
    return identifier_ok and all(number in text for number in numbers) and all(operator in text for operator in operators)


def _issue(
    issue_id: str,
    axis: Literal["epistemic_safety", "publication_utility"],
    scope: Literal["sentence", "claim", "stage", "section", "document"],
    code: str,
    message: str,
    *,
    section_id: str = "",
    claim_id: str = "",
    stage_id: str = "",
) -> PublicationQualityIssueV1:
    return PublicationQualityIssueV1(
        issue_id=issue_id,
        axis=axis,
        scope=scope,
        code=code,
        message=message,
        section_id=section_id,
        claim_id=claim_id,
        stage_id=stage_id,
    )


__all__ = [
    "EpistemicSafetyMetricsV1",
    "PublicationQualityIssueV1",
    "PublicationQualityReportV1",
    "PublicationUtilityMetricsV1",
    "evaluate_publication_method_quality",
]
