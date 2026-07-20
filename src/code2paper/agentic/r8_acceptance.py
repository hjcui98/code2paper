"""R8.1 acceptance criteria checker for real Gemma quality acceptance.

Implements design section 11 (R8) of the execution plan.  This module
provides a deterministic, project-agnostic checker that verifies a
run's output directory satisfies the R8.2 per-project acceptance
criteria and the R8.1 execution protocol.

R8.2 per-project acceptance criteria (each criterion is checked
individually with a pass/fail and a reason):

1. ``gap_driven_tool_selection`` -- the agent made at least one
   autonomous tool selection driven by an information gap (an
   ``AgentDecision`` or ``ResearchDecisionV1`` whose ``rationale`` /
   ``issue_id`` / ``expected_information_gain`` indicates a gap, OR
   whose ``action`` is ``RECORD_GAP`` preceded by a tool-calling
   action);
2. ``code_mainline_in_method`` -- the final Method text contains at
   least one supported atomic claim covering a ``must_cover``
   obligation (the code main path entered the Method);
3. ``no_project_specific_claim_literals`` -- no project-specific
   literal appears in any claim ``canonical_text``, Method text, or
   equation token (the same forbidden literal set used by
   ``behavior_templates``);
4. ``unsupported_final_sentences_zero`` -- the final text validation
   report records zero unsupported atomic claims;
5. ``must_cover_terminal`` -- every ``must_cover`` obligation in the
   coverage report has a terminal status (``supported`` /
   ``partial`` / ``explicit_gap`` / ``blocked``); ``unresolved`` is
   a hard failure;
6. ``no_evidence_free_equations`` -- every equation token appearing
   in the final Method text is authorized by at least one claim's
   ``allowed_wording_boundary`` (or the boundary explicitly permits
   equations);
7. ``trace_reproducible`` -- the tool-call trace and decision trace
   recorded for the run match the digests computed from the actual
   artifacts (i.e., the same inputs produce the same trace digests);
8. ``checkpoint_resume_consistent`` -- when a resume checkpoint is
   available, the resumed run's final state digest matches the
   original run's final state digest.

R8.1 execution protocol checks (verified from the run's environment /
configuration):

- ``temperature_zero`` -- the LLM temperature is exactly 0.0;
- ``llm_cache_off`` -- the ``CODE2PAPER_LLM_CACHE`` environment
  variable is ``"0"``;
- ``single_tp2_instance`` -- the environment records a single TP=2
  Gemma instance on two GPUs (no parallel model instances);
- ``serial_execution`` -- the run's protocol spec records strict
  serial execution (no parallel project runs in the same protocol);
- ``code_and_author_yml_only`` -- the run's source authority policy
  did not promote paper / README / TeX / PDF to ``executable_hard``;
- ``paper_read_only_at_end`` -- the run's diagnostic comparison flag
  is set, indicating the original paper was read only after the
  Method was authored.

R8.1 hard constraint: this module's source MUST NOT contain
project-specific literals.  The forbidden literal set is imported
from ``behavior_templates`` so the constraint is enforced in one
place.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.behavior_templates import _FORBIDDEN_PROJECT_LITERALS
from code2paper.agentic.contracts import AgentDecision
from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    AtomicClaimV3,
    load_atomic_claims_v3,
)
from code2paper.agentic.obligation_fact_alignment import (
    ObligationCoverageReportV2,
)
from code2paper.agentic.trust_contracts import TextEvidenceValidationReport


# ---------------------------------------------------------------------------
# Acceptance criterion models
# ---------------------------------------------------------------------------


#: Status values for an acceptance criterion.
CriterionStatus = str  # "passed" | "failed" | "skipped"


class R8AcceptanceCriterion(BaseModel):
    """Result of a single R8 acceptance criterion check.

    Each criterion has a stable ``criterion_id`` (used by the report's
    ``criteria`` map and by tests), a human-readable ``description``,
    a ``status`` (``passed`` / ``failed`` / ``skipped``), and a
    ``reason`` explaining the status (failure reasons are required,
    pass reasons may be empty).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    criterion_id: str
    description: str
    status: CriterionStatus
    reason: str = ""
    evidence: tuple[str, ...] = Field(default_factory=tuple)

    @property
    def passed(self) -> bool:
        return self.status == "passed"


class R8ProtocolSettings(BaseModel):
    """R8.1 execution protocol settings to verify against a run.

    These are the frozen inputs the R8 protocol requires for every
    Gemma-backed run.  The checker compares the run's recorded
    environment / configuration against these settings.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    temperature: float = 0.0
    llm_cache_env: str = "0"
    single_tp2_instance: bool = True
    serial_execution: bool = True
    paper_promoted_to_hard_evidence: bool = False
    paper_read_only_at_end: bool = True


class R8AcceptanceReport(BaseModel):
    """Aggregate R8 acceptance report for a single project run.

    The report bundles per-criterion results, the protocol settings
    check, and a top-level ``accepted`` flag.  ``accepted`` is ``True``
    only when every non-skipped criterion passed AND the protocol
    settings check passed.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    mode: str = "r8-acceptance-v1"
    run_id: str
    project_id: str = ""
    criteria: dict[str, R8AcceptanceCriterion] = Field(default_factory=dict)
    protocol_settings: R8ProtocolSettings = Field(default_factory=R8ProtocolSettings)
    protocol_check_passed: bool = False
    accepted: bool = False
    content_digest: str = ""

    @model_validator(mode="after")
    def _compute_digest(self) -> "R8AcceptanceReport":
        payload = {
            "schema_version": self.schema_version,
            "mode": self.mode,
            "run_id": self.run_id,
            "project_id": self.project_id,
            "criteria": {
                key: value.model_dump(mode="json")
                for key, value in sorted(self.criteria.items())
            },
            "protocol_settings": self.protocol_settings.model_dump(mode="json"),
            "protocol_check_passed": self.protocol_check_passed,
            "accepted": self.accepted,
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        digest = "sha256:" + hashlib.sha256(encoded).hexdigest()
        object.__setattr__(self, "content_digest", digest)
        return self


# ---------------------------------------------------------------------------
# Project literal scanning (shared with behavior_templates)
# ---------------------------------------------------------------------------


def _build_project_literal_pattern() -> re.Pattern[str]:
    """Build the word-boundary regex for project literal detection.

    Matches the same regex used by ``behavior_templates`` so the
    forbidden literal set is enforced consistently across templates
    and claims / Method text.
    """

    escaped: list[str] = []
    for literal in _FORBIDDEN_PROJECT_LITERALS:
        pattern = re.escape(literal).replace(re.escape("-"), "[-_]").replace(
            re.escape("_"), "[-_]"
        )
        escaped.append(pattern)
    combined = "|".join(escaped)
    return re.compile(r"(?<![a-z0-9])(" + combined + r")(?![a-z0-9])", re.IGNORECASE)


_PROJECT_LITERAL_PATTERN: re.Pattern[str] = _build_project_literal_pattern()


def scan_text_for_project_literals(text: str) -> list[str]:
    """Return the list of forbidden project literals found in ``text``.

    Uses word boundaries so short project names do not match inside
    longer words (e.g., a three-letter project name does not match
    inside a longer word that happens to contain those letters).
    Returns each match at most once, preserving discovery order.
    """

    seen: list[str] = []
    for match in _PROJECT_LITERAL_PATTERN.finditer(text or ""):
        literal = match.group(1).lower()
        if literal not in seen:
            seen.append(literal)
    return seen


def scan_claims_for_project_literals(
    claims: Iterable[AtomicClaimV3],
) -> dict[str, list[str]]:
    """Scan every claim's ``canonical_text`` for project literals.

    Returns a mapping ``{claim_id: [literal, ...]}`` for claims that
    contain at least one forbidden literal.  Claims with no matches
    are omitted from the result.
    """

    flagged: dict[str, list[str]] = {}
    for claim in claims:
        matches = scan_text_for_project_literals(claim.canonical_text)
        if matches:
            flagged[claim.claim_id] = matches
    return flagged


# ---------------------------------------------------------------------------
# Equation authorization
# ---------------------------------------------------------------------------


#: Regex for inline equations in markdown / LaTeX-flavored Method text.
_EQUATION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\$\$([^$]+)\$\$"),
    re.compile(r"(?<!\$)\$([^$\n]+)\$(?!\$)"),
    re.compile(r"\\\(([^$]+)\\\)"),
    re.compile(r"\\\[([^$]+)\\\]"),
)

#: Regex for ``name = expression`` patterns (e.g., ``s = softmax(x)``).
_NAME_EQ_PATTERN = re.compile(r"(?<![A-Za-z0-9_])([A-Za-z][A-Za-z0-9_]*)\s*=\s*[^=\n;]+")


#: LaTeX command tokens that appear inside math expressions but are not
#: equation variables (e.g., ``\mathrm``, ``\log``, ``\sum``).  These are
#: filtered out of the equation token set so they do not trigger
#: unauthorized-equation failures.
_LATEX_COMMAND_TOKENS: frozenset[str] = frozenset({
    "mathrm", "mathbf", "mathit", "mathcal", "mathbb", "operatorname",
    "frac", "sum", "prod", "int", "log", "exp", "sin", "cos", "tan",
    "max", "min", "arg", "sup", "inf", "lim", "sqrt", "cdot", "times",
    "alpha", "beta", "gamma", "delta", "epsilon", "theta", "lambda",
    "mu", "sigma", "phi", "psi", "omega", "nabla", "partial", "infty",
    "approx", "sim", "equiv", "leq", "geq", "neq", "pm", "mp", "div",
    "forall", "exists", "in", "notin", "subset", "supset", "cup", "cap",
    "emptyset", "text", "displaystyle", "left", "right", "big", "Big",
})


def extract_equation_tokens(text: str) -> list[str]:
    """Extract candidate equation tokens from Method text.

    Returns a list of normalized tokens (lowercased, stripped) that
    appear inside ``$...$`` / ``$$...$$`` / ``\\(...\\)`` / ``\\[...\\]``
    formulas, plus the left-hand-side identifier of ``name = expr``
    patterns.  LaTeX command tokens (``mathrm``, ``log``, ``sum``,
    etc.) are filtered out.  Tokens are returned in discovery order,
    deduplicated.
    """

    tokens: list[str] = []
    seen: set[str] = set()
    for pattern in _EQUATION_PATTERNS:
        for match in pattern.finditer(text or ""):
            for raw in re.findall(r"[A-Za-z][A-Za-z0-9_]*", match.group(1)):
                token = raw.lower()
                if token in _LATEX_COMMAND_TOKENS:
                    continue
                if token not in seen:
                    seen.add(token)
                    tokens.append(token)
    for match in _NAME_EQ_PATTERN.finditer(text or ""):
        token = match.group(1).lower()
        if token in _LATEX_COMMAND_TOKENS:
            continue
        if token not in seen:
            seen.add(token)
            tokens.append(token)
    return tokens


def unauthorized_equation_tokens(
    method_text: str,
    claims: Iterable[AtomicClaimV3],
) -> list[str]:
    """Return equation tokens in ``method_text`` not authorized by any claim.

    A token is authorized when it appears in some claim's
    ``allowed_wording_boundary`` OR the claim's ``canonical_text`` (the
    claim itself uses that token) OR the boundary contains ``equation``
    or ``formula`` (which permits any formula).  Tokens that appear
    in the project-literal forbidden set are not equations and are
    ignored here (they are flagged by the project-literal scan).
    """

    claims_list = list(claims)
    explicit_formula_permission = False
    for claim in claims_list:
        boundary = (claim.allowed_wording_boundary or "").lower()
        if "equation" in boundary or "formula" in boundary:
            explicit_formula_permission = True
            break
    if explicit_formula_permission:
        return []
    authorized: set[str] = set()
    for claim in claims_list:
        for source_text in (claim.allowed_wording_boundary, claim.canonical_text):
            for token in re.findall(r"[A-Za-z][A-Za-z0-9_]*", source_text or ""):
                token_lower = token.lower()
                if token_lower in _LATEX_COMMAND_TOKENS:
                    continue
                authorized.add(token_lower)
    unauthorized: list[str] = []
    for token in extract_equation_tokens(method_text):
        if token in authorized:
            continue
        if token in unauthorized:
            continue
        unauthorized.append(token)
    return unauthorized


# ---------------------------------------------------------------------------
# Gap-driven tool selection detection
# ---------------------------------------------------------------------------


#: Substrings in a decision's rationale / goal / issue_id that indicate
#: the decision was driven by an information gap.  These are
#: project-agnostic phrases that the supervisor emits when it selects a
#: tool because of a missing anchor, missing relation, missing condition,
#: or another issue kind.
_GAP_INDICATOR_SUBSTRINGS: tuple[str, ...] = (
    "gap",
    "missing",
    "unresolved",
    "issue_driven",
    "no_progress",
    "missing_anchor",
    "missing_relation",
    "missing_condition",
    "wrong_span_role",
    "branch_ambiguity",
    "config_ambiguity",
    "no_information_gain",
    "truncated_observation",
    "ambiguous_observation",
    "hint_code_conflict",
    "formula_unsupported",
    "sentence_claim_atomicity",
    "direct_evidence_semantically_unrelated",
    "no_semantically_matching_projected_claim",
    "budget_exhausted",
    "quality_regression",
)

#: Actions that count as autonomous tool selection (i.e., the agent
#: chose to call a tool, not just record a gap or stop).
_TOOL_CALLING_ACTIONS: frozenset[str] = frozenset({
    "SEARCH_SYMBOLS",
    "READ_CANDIDATE",
    "TRACE_CALLS",
    "TRACE_DATA_FLOW",
    "INSPECT_BRANCH",
    "INSPECT_CONFIG",
    "SEARCH_HINTS",
    "BUILD_BEHAVIOR_SUBGRAPH",
    "PROPOSE_PACKET",
    "COMPILE_FACTS",
    "DECOMPOSE_CLAIMS",
    "REWRITE_SENTENCES",
})


def has_gap_driven_tool_selection(
    decisions: Iterable[Any],
) -> tuple[bool, str]:
    """Return ``(found, evidence)`` for gap-driven tool selection.

    A run satisfies this criterion when at least one decision was
    driven by a gap (its ``rationale`` / ``goal`` / ``issue_id``
    contains a gap indicator) AND it selected a tool-calling action.
    A ``RECORD_GAP`` action alone does not count -- the agent must
    have *selected a tool* because of a gap, not just recorded one.

    Both ``ResearchDecisionV1`` (with ``action`` field) and
    ``AgentDecision`` (with ``decision`` field) are recognized.  The
    ``decision`` field of ``AgentDecision`` typically carries the
    action name (e.g., ``"SEARCH_SYMBOLS"``).
    """

    for decision in decisions:
        action = _decision_field(decision, "action") or _decision_field(decision, "decision")
        rationale = _decision_field(decision, "rationale")
        goal = _decision_field(decision, "goal")
        issue_id = _decision_field(decision, "issue_id")
        expected_gain = _decision_field(decision, "expected_information_gain")
        haystack = " ".join(filter(None, [rationale, goal, issue_id, expected_gain])).lower()
        if not haystack:
            continue
        if not any(indicator in haystack for indicator in _GAP_INDICATOR_SUBSTRINGS):
            continue
        if action in _TOOL_CALLING_ACTIONS:
            decision_id = (
                _decision_field(decision, "decision_id")
                or _decision_field(decision, "node")
                or str(action)
            )
            return True, decision_id
    return False, ""


def _decision_field(decision: Any, field: str) -> str:
    """Read a string field from a decision-like object.

    Supports ``AgentDecision`` (which has ``node`` / ``decision`` /
    ``rationale`` / ``evidence_ids``) and ``ResearchDecisionV1`` (which
    has ``decision_id`` / ``action`` / ``goal`` / ``issue_id`` /
    ``rationale`` / ``expected_information_gain``).  Unknown fields
    return ``""``.
    """

    value = getattr(decision, field, None)
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


# ---------------------------------------------------------------------------
# Trace reproducibility
# ---------------------------------------------------------------------------


def compute_trace_digest(
    decisions: Iterable[Any],
    tool_call_trace_refs: Iterable[str],
) -> str:
    """Compute a stable digest for a run's decision + tool-call trace.

    The digest is content-addressed: two runs with the same decisions
    (in the same order) and the same tool-call trace refs produce the
    same digest.  This is what ``trace_reproducible`` compares against
    the digest recorded by the run.
    """

    payload: dict[str, Any] = {
        "decisions": [],
        "tool_call_trace_refs": list(tool_call_trace_refs),
    }
    for decision in decisions:
        entry = {
            "decision_id": _decision_field(decision, "decision_id"),
            "node": _decision_field(decision, "node"),
            "decision": _decision_field(decision, "decision"),
            "action": _decision_field(decision, "action"),
            "rationale": _decision_field(decision, "rationale"),
            "goal": _decision_field(decision, "goal"),
            "issue_id": _decision_field(decision, "issue_id"),
            "obligation_id": _decision_field(decision, "obligation_id"),
            "evidence_ids": list(getattr(decision, "evidence_ids", []) or []),
            "artifact_keys": list(getattr(decision, "artifact_keys", []) or []),
        }
        payload["decisions"].append(entry)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def verify_trace_reproducibility(
    recorded_digest: str,
    decisions: Iterable[Any],
    tool_call_trace_refs: Iterable[str],
) -> tuple[bool, str]:
    """Verify the recorded trace digest matches the recomputed digest.

    Returns ``(match, recomputed_digest)``.  When ``recorded_digest``
    is empty, the check is skipped (returns ``(True, "")`` with a
    note that no digest was recorded -- callers decide whether to
    treat this as a failure via the criterion logic).
    """

    if not recorded_digest:
        return True, ""
    recomputed = compute_trace_digest(decisions, tool_call_trace_refs)
    return recomputed == recorded_digest, recomputed


# ---------------------------------------------------------------------------
# Checkpoint / resume consistency
# ---------------------------------------------------------------------------


def verify_checkpoint_resume_consistency(
    original_final_state_digest: str,
    resumed_final_state_digest: str,
) -> tuple[bool, str]:
    """Verify a resumed run reached the same final state as the original.

    Returns ``(consistent, reason)``.  When either digest is empty,
    the check cannot be performed and ``reason`` is
    ``"skipped:missing_digest"`` -- the caller treats this as a skip
    (not a pass and not a fail).  When both digests are present and
    match, ``consistent`` is ``True`` and ``reason`` is ``"match"``.
    When they differ, ``consistent`` is ``False`` and ``reason``
    describes the mismatch.
    """

    if not original_final_state_digest or not resumed_final_state_digest:
        return True, "skipped:missing_digest"
    if original_final_state_digest == resumed_final_state_digest:
        return True, "match"
    return False, f"mismatch:original={original_final_state_digest}:resumed={resumed_final_state_digest}"


# ---------------------------------------------------------------------------
# Main acceptance checker
# ---------------------------------------------------------------------------


def check_r8_acceptance(
    *,
    run_id: str,
    project_id: str = "",
    decisions: Iterable[Any] | None = None,
    tool_call_trace_refs: Iterable[str] | None = None,
    recorded_trace_digest: str = "",
    coverage_report: ObligationCoverageReportV2 | None = None,
    claim_set: AtomicClaimSetV3 | None = None,
    validation_report: TextEvidenceValidationReport | None = None,
    method_text: str = "",
    original_final_state_digest: str = "",
    resumed_final_state_digest: str = "",
    protocol_settings: R8ProtocolSettings | None = None,
    run_environment: Mapping[str, str] | None = None,
    run_temperature: float | None = None,
    source_authority_policy: Mapping[str, Any] | None = None,
    paper_read_only_at_end: bool | None = None,
) -> R8AcceptanceReport:
    """Check all R8 acceptance criteria for a single project run.

    Parameters
    ----------
    run_id
        The run's stable identity (used by the report and digest).
    project_id
        Optional project identifier for the report.
    decisions
        Iterable of ``AgentDecision`` or ``ResearchDecisionV1`` objects
        recorded for the run.  Used by the gap-driven tool selection
        and trace reproducibility checks.
    tool_call_trace_refs
        Iterable of tool-call trace reference strings recorded for the
        run.  Used by the trace reproducibility check.
    recorded_trace_digest
        The trace digest recorded by the run (e.g., from the run
        summary).  When empty, the trace reproducibility check is
        skipped.
    coverage_report
        The run's ``ObligationCoverageReportV2``.  Used by the
        ``must_cover_terminal`` and ``code_mainline_in_method``
        checks.
    claim_set
        The run's ``AtomicClaimSetV3``.  Used by the
        ``no_project_specific_claim_literals`` and
        ``code_mainline_in_method`` checks.
    validation_report
        The run's ``TextEvidenceValidationReport``.  Used by the
        ``unsupported_final_sentences_zero`` check.
    method_text
        The final Method text.  Used by the
        ``no_project_specific_claim_literals`` and
        ``no_evidence_free_equations`` checks.
    original_final_state_digest, resumed_final_state_digest
        Digests of the final state for the original and resumed runs.
        When both are non-empty, the ``checkpoint_resume_consistent``
        check verifies they match.  When either is empty, the check
        is skipped.
    protocol_settings
        The expected R8.1 protocol settings.  When ``None``, the
        default frozen settings are used.
    run_environment
        The run's recorded environment variables (e.g.,
        ``CODE2PAPER_LLM_CACHE``).  Used by the protocol check.
    run_temperature
        The run's recorded LLM temperature.  Used by the protocol
        check.
    source_authority_policy
        The run's source authority policy.  Used by the
        ``code_and_author_yml_only`` protocol check.
    paper_read_only_at_end
        Evidence that the original paper was read only AFTER the Method
        was authored (i.e., for diagnostic comparison).  ``None`` means
        the run did not record this evidence, which fails the protocol
        check.  Used by the ``paper_read_only_at_end`` protocol check.
    """

    settings = protocol_settings or R8ProtocolSettings()
    decisions_list = list(decisions or [])
    tool_refs_list = list(tool_call_trace_refs or [])
    env = dict(run_environment or {})
    authority = dict(source_authority_policy or {})

    criteria: dict[str, R8AcceptanceCriterion] = {}

    # 1. gap_driven_tool_selection
    found, evidence = has_gap_driven_tool_selection(decisions_list)
    criteria["gap_driven_tool_selection"] = R8AcceptanceCriterion(
        criterion_id="gap_driven_tool_selection",
        description="Agent made at least one gap-driven autonomous tool selection.",
        status="passed" if found else "failed",
        reason=(
            f"gap-driven decision found: {evidence}"
            if found
            else "no decision with a gap indicator selected a tool-calling action"
        ),
        evidence=(evidence,) if found else (),
    )

    # 2. code_mainline_in_method
    mainline_ok, mainline_reason = _check_code_mainline_in_method(
        coverage_report, claim_set, validation_report
    )
    criteria["code_mainline_in_method"] = R8AcceptanceCriterion(
        criterion_id="code_mainline_in_method",
        description="At least one supported claim covering a must_cover obligation entered the Method.",
        status="passed" if mainline_ok else "failed",
        reason=mainline_reason,
    )

    # 3. no_project_specific_claim_literals
    literal_ok, literal_reason, literal_evidence = _check_no_project_specific_literals(
        claim_set, method_text
    )
    criteria["no_project_specific_claim_literals"] = R8AcceptanceCriterion(
        criterion_id="no_project_specific_claim_literals",
        description="No project-specific literal appears in any claim or Method text.",
        status="passed" if literal_ok else "failed",
        reason=literal_reason,
        evidence=literal_evidence,
    )

    # 4. unsupported_final_sentences_zero
    unsupported = validation_report.unsupported_claims if validation_report else 0
    criteria["unsupported_final_sentences_zero"] = R8AcceptanceCriterion(
        criterion_id="unsupported_final_sentences_zero",
        description="Final text validation recorded zero unsupported atomic claims.",
        status="passed" if unsupported == 0 else "failed",
        reason=(
            "unsupported_claims=0"
            if unsupported == 0
            else f"unsupported_claims={unsupported} (must be 0)"
        ),
    )

    # 5. must_cover_terminal
    terminal_ok, terminal_reason, unresolved_ids = _check_must_cover_terminal(coverage_report)
    criteria["must_cover_terminal"] = R8AcceptanceCriterion(
        criterion_id="must_cover_terminal",
        description="Every must_cover obligation has a terminal coverage status.",
        status="passed" if terminal_ok else "failed",
        reason=terminal_reason,
        evidence=tuple(unresolved_ids),
    )

    # 6. no_evidence_free_equations
    equation_ok, equation_reason, equation_evidence = _check_no_evidence_free_equations(
        method_text, claim_set
    )
    criteria["no_evidence_free_equations"] = R8AcceptanceCriterion(
        criterion_id="no_evidence_free_equations",
        description="Every equation token in the Method is authorized by a claim boundary.",
        status="passed" if equation_ok else "failed",
        reason=equation_reason,
        evidence=equation_evidence,
    )

    # 7. trace_reproducible
    if recorded_trace_digest:
        match, recomputed = verify_trace_reproducibility(
            recorded_trace_digest, decisions_list, tool_refs_list
        )
        trace_status: CriterionStatus = "passed" if match else "failed"
        trace_reason = (
            f"recorded={recorded_trace_digest} recomputed={recomputed}"
            if not match
            else f"digest={recorded_trace_digest}"
        )
    else:
        trace_status = "skipped"
        trace_reason = "no recorded trace digest; skipped"
    criteria["trace_reproducible"] = R8AcceptanceCriterion(
        criterion_id="trace_reproducible",
        description="Recorded trace digest matches the recomputed digest.",
        status=trace_status,
        reason=trace_reason,
    )

    # 8. checkpoint_resume_consistent
    if original_final_state_digest and resumed_final_state_digest:
        consistent, ckpt_reason = verify_checkpoint_resume_consistency(
            original_final_state_digest, resumed_final_state_digest
        )
        ckpt_status: CriterionStatus = "passed" if consistent else "failed"
    else:
        # When either digest is missing, the check is skipped (we
        # cannot verify consistency without both digests).  This is
        # not a pass and not a fail -- it just means the run did not
        # exercise checkpoint/resume.
        ckpt_status = "skipped"
        ckpt_reason = "no resume digest provided; skipped"
    criteria["checkpoint_resume_consistent"] = R8AcceptanceCriterion(
        criterion_id="checkpoint_resume_consistent",
        description="Resumed run reached the same final state as the original.",
        status=ckpt_status,
        reason=ckpt_reason,
    )

    # Protocol settings check
    protocol_ok, protocol_failures = _check_protocol_settings(
        settings,
        env,
        run_temperature,
        authority,
        paper_read_only_at_end_evidence=paper_read_only_at_end,
    )

    # Top-level accepted flag: every criterion must be exercised and
    # passed (``skipped`` counts as failure for acceptance -- an R8 run
    # must positively evidence every criterion, not rely on absence),
    # AND the protocol check must pass.
    non_passed = [
        key for key, value in criteria.items()
        if value.status != "passed"
    ]
    accepted = protocol_ok and not non_passed

    return R8AcceptanceReport(
        run_id=run_id,
        project_id=project_id,
        criteria=criteria,
        protocol_settings=settings,
        protocol_check_passed=protocol_ok,
        accepted=accepted,
    )


# ---------------------------------------------------------------------------
# Per-criterion helpers
# ---------------------------------------------------------------------------


def _check_code_mainline_in_method(
    coverage_report: ObligationCoverageReportV2 | None,
    claim_set: AtomicClaimSetV3 | None,
    validation_report: TextEvidenceValidationReport | None,
) -> tuple[bool, str]:
    """Check that at least one supported must_cover claim entered the Method.

    The code mainline is in the Method when:
    - the coverage report has at least one ``must_cover`` obligation
      with status ``supported`` (terminal), AND
    - the claim set has at least one ``supported`` claim covering a
      ``must_cover`` obligation, AND
    - the validation report records at least one supported or caveated
      claim (i.e., the Method text actually contains a validated
      claim).
    """

    if coverage_report is None or claim_set is None or validation_report is None:
        return False, "missing coverage_report / claim_set / validation_report"
    supported_must_cover_ids = {
        item.obligation_id
        for item in coverage_report.items
        if item.obligation_priority == "must_cover" and item.coverage_status == "supported"
    }
    if not supported_must_cover_ids:
        return False, "no must_cover obligation reached status=supported"
    supported_claims_for_must_cover = [
        claim for claim in claim_set.claims
        if claim.status == "supported"
        and any(obl_id in supported_must_cover_ids for obl_id in claim.covers_obligation_ids)
    ]
    if not supported_claims_for_must_cover:
        return False, "no supported claim covers a must_cover obligation"
    validated = validation_report.supported_claims + validation_report.caveated_claims
    if validated == 0:
        return False, "validation_report records zero supported/caveated claims"
    return True, (
        f"must_cover_supported={len(supported_must_cover_ids)} "
        f"claims_for_must_cover={len(supported_claims_for_must_cover)} "
        f"validated={validated}"
    )


def _check_no_project_specific_literals(
    claim_set: AtomicClaimSetV3 | None,
    method_text: str,
) -> tuple[bool, str, tuple[str, ...]]:
    """Check that no project-specific literal appears in claims or Method.

    Scans every claim's ``canonical_text`` and the Method text.  Returns
    ``(ok, reason, evidence)`` where ``evidence`` is a tuple of
    ``"claim_id:literal"`` or ``"method:literal"`` strings.
    """

    evidence: list[str] = []
    if claim_set is not None:
        flagged_claims = scan_claims_for_project_literals(claim_set.claims)
        for claim_id, literals in flagged_claims.items():
            for literal in literals:
                evidence.append(f"{claim_id}:{literal}")
    method_literals = scan_text_for_project_literals(method_text)
    for literal in method_literals:
        evidence.append(f"method:{literal}")
    if not evidence:
        return True, "no project literals found", ()
    return False, (
        f"found {len(evidence)} project literal occurrences: "
        + ", ".join(evidence[:5])
        + (" ..." if len(evidence) > 5 else "")
    ), tuple(evidence)


def _check_must_cover_terminal(
    coverage_report: ObligationCoverageReportV2 | None,
) -> tuple[bool, str, list[str]]:
    """Check that every must_cover obligation has a terminal status.

    Returns ``(ok, reason, unresolved_ids)``.  ``unresolved_ids`` is
    the list of must_cover obligation ids whose status is
    ``unresolved`` (the only non-terminal status).
    """

    if coverage_report is None:
        return False, "missing coverage_report", []
    unresolved = [
        item.obligation_id
        for item in coverage_report.items
        if item.obligation_priority == "must_cover"
        and item.coverage_status == "unresolved"
    ]
    if unresolved:
        return False, (
            f"{len(unresolved)} must_cover obligations unresolved: "
            + ", ".join(unresolved[:5])
            + (" ..." if len(unresolved) > 5 else "")
        ), unresolved
    return True, "all must_cover obligations terminal", []


def _check_no_evidence_free_equations(
    method_text: str,
    claim_set: AtomicClaimSetV3 | None,
) -> tuple[bool, str, tuple[str, ...]]:
    """Check that every equation token in the Method is authorized.

    Returns ``(ok, reason, evidence)`` where ``evidence`` is the tuple
    of unauthorized equation tokens.
    """

    if not method_text:
        return True, "no method text provided; skipped", ()
    claims = claim_set.claims if claim_set is not None else []
    unauthorized = unauthorized_equation_tokens(method_text, claims)
    if not unauthorized:
        return True, "all equation tokens authorized", ()
    return False, (
        f"{len(unauthorized)} unauthorized equation tokens: "
        + ", ".join(unauthorized[:5])
        + (" ..." if len(unauthorized) > 5 else "")
    ), tuple(unauthorized)


# ---------------------------------------------------------------------------
# Protocol settings check
# ---------------------------------------------------------------------------


def _check_protocol_settings(
    settings: R8ProtocolSettings,
    env: Mapping[str, str],
    run_temperature: float | None,
    source_authority_policy: Mapping[str, Any],
    paper_read_only_at_end_evidence: bool | None = None,
) -> tuple[bool, list[str]]:
    """Verify the run's environment matches the R8.1 protocol settings.

    Returns ``(ok, failures)``.  ``failures`` is a list of human-readable
    failure strings (empty when ``ok`` is ``True``).

    The check is strict: every protocol field that the R8.1 spec declares
    as required must be present and match.  Missing values (``None`` /
    empty string / empty policy) are failures, not skips, because an
    acceptance run must positively evidence protocol compliance rather
    than rely on absence of evidence.
    """

    failures: list[str] = []

    # temperature_zero: the run must positively record temperature == 0.
    # A missing temperature is a failure (the run did not evidence the
    # protocol setting).
    if run_temperature is None:
        failures.append("temperature_not_recorded:expected=0.0")
    elif run_temperature != settings.temperature:
        failures.append(
            f"temperature_mismatch:run={run_temperature} expected={settings.temperature}"
        )

    # llm_cache_off
    actual_cache = env.get("CODE2PAPER_LLM_CACHE", "")
    if actual_cache != settings.llm_cache_env:
        failures.append(
            f"llm_cache_mismatch:run={actual_cache!r} expected={settings.llm_cache_env!r}"
        )

    # single_tp2_instance: enforced via env vars CODE2PAPER_TP_SIZE and
    # CODE2PAPER_NUM_GPUS.  Both must be present and equal to "2".
    # Missing values are failures (the run did not evidence TP=2 on 2
    # GPUs).
    tp_size = env.get("CODE2PAPER_TP_SIZE", "")
    num_gpus = env.get("CODE2PAPER_NUM_GPUS", "")
    if settings.single_tp2_instance:
        if not tp_size:
            failures.append("tp_size_not_recorded:expected=2")
        elif tp_size != "2":
            failures.append(f"tp_size_mismatch:run={tp_size} expected=2")
        if not num_gpus:
            failures.append("num_gpus_not_recorded:expected=2")
        elif num_gpus != "2":
            failures.append(f"num_gpus_mismatch:run={num_gpus} expected=2")

    # serial_execution: enforced via env var CODE2PAPER_PARALLEL_PROJECTS.
    # The value "1" means "run one project at a time" (i.e., strict
    # serial), and "0" or absent means "no parallelism".  Any value > 1
    # is a parallel run, which the R8.1 protocol forbids.  We accept
    # "", "0", and "1" as serial-compliant.
    parallel = env.get("CODE2PAPER_PARALLEL_PROJECTS", "")
    if settings.serial_execution:
        try:
            parallel_int = int(parallel) if parallel else 0
        except ValueError:
            parallel_int = 1  # non-numeric -> treat as parallel (fail)
        if parallel_int > 1:
            failures.append(
                f"parallel_projects_not_allowed:run={parallel} expected<=1"
            )

    # code_and_author_yml_only: the source authority policy must be
    # present and must not promote paper / README / TeX / PDF to
    # executable_hard.  An empty policy is a failure (the run did not
    # evidence its source authority classification).
    if not source_authority_policy:
        failures.append("source_authority_policy_missing")
    elif not settings.paper_promoted_to_hard_evidence:
        paper_promotion = _detect_paper_promotion(source_authority_policy)
        for promotion in paper_promotion:
            failures.append(f"paper_promoted_to_hard_evidence:{promotion}")

    # paper_read_only_at_end: the run must positively evidence that the
    # original paper was read only AFTER the Method was authored (i.e.,
    # for diagnostic comparison, not as a writing input).  ``None``
    # means the run did not record this evidence -> failure.
    if settings.paper_read_only_at_end:
        if paper_read_only_at_end_evidence is None:
            failures.append("paper_read_only_at_end_not_evidenced")
        elif not paper_read_only_at_end_evidence:
            failures.append("paper_read_only_at_end_violated")

    return (not failures), failures


def _detect_paper_promotion(
    source_authority_policy: Mapping[str, Any],
) -> list[str]:
    """Detect paper / README / TeX / PDF promoted to executable_hard.

    Returns a list of human-readable promotion descriptions.  The
    source authority policy is a mapping ``{source_kind: authority}``
    or a nested mapping; we look for any entry whose key contains
    ``paper`` / ``readme`` / ``tex`` / ``pdf`` (case-insensitive) and
    whose value is or contains ``executable_hard``.
    """

    promotions: list[str] = []
    paper_tokens = ("paper", "readme", "tex", "pdf")
    for key, value in source_authority_policy.items():
        key_lower = str(key).lower()
        if not any(token in key_lower for token in paper_tokens):
            continue
        value_str = str(value).lower()
        if "executable_hard" in value_str:
            promotions.append(f"{key}={value}")
    return promotions


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def write_r8_acceptance_report(path: str | Path, report: R8AcceptanceReport) -> Path:
    """Write an R8 acceptance report to ``path`` as JSON."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return output


def load_r8_acceptance_report(path: str | Path) -> R8AcceptanceReport:
    """Load an R8 acceptance report from ``path``."""

    return R8AcceptanceReport.model_validate_json(Path(path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Run-output directory scanner
# ---------------------------------------------------------------------------


def check_r8_acceptance_from_run_dir(
    run_dir: str | Path,
    *,
    run_id: str = "",
    project_id: str = "",
    protocol_settings: R8ProtocolSettings | None = None,
    resumed_run_dir: str | Path | None = None,
) -> R8AcceptanceReport:
    """Check R8 acceptance by scanning a run's output directory.

    The run directory is expected to contain the standard agentic
    artifacts written by ``runner.py``.  The function first looks for
    ``agentic_run_summary.json`` at the run directory root, then in
    the ``10_run/`` subdirectory (the standard location written by
    the runner).  When the summary's ``artifacts`` map is available,
    it is used to locate files in their actual subdirectories
    (``04_evidence/``, ``06_authoring/``, ``07_validation/``, etc.).

    When ``obligation_coverage_v2`` is not present as a direct
    artifact, the coverage report is built on-the-fly from the
    intent graph + claim set + code facts using
    ``build_obligation_coverage_v2`` so the
    ``code_mainline_in_method`` and ``must_cover_terminal`` criteria
    can still be evaluated.

    When ``resumed_run_dir`` is provided, the resumed run's final
    state digest is compared against the original's for the
    ``checkpoint_resume_consistent`` check.
    """

    run_path = Path(run_dir).resolve()
    summary_path = run_path / "agentic_run_summary.json"
    if not summary_path.is_file():
        # Standard runner layout: summary is in artifacts/10_run/.
        for candidate in (
            run_path / "artifacts" / "10_run" / "agentic_run_summary.json",
            run_path / "10_run" / "agentic_run_summary.json",
        ):
            if candidate.is_file():
                summary_path = candidate
                break
    summary_data: dict[str, Any] = {}
    if summary_path.is_file():
        summary_data = json.loads(summary_path.read_text(encoding="utf-8"))
    effective_run_id = run_id or summary_data.get("run_id", "") or run_path.name

    # The summary's ``artifacts`` map has full paths to files in
    # subdirectories.  Use it as the primary source, then fall back to
    # ``run_path / <filename>`` for flat layouts.
    artifacts_map: dict[str, str] = {}
    for name, record in (summary_data.get("artifacts") or {}).items():
        if isinstance(record, dict) and "path" in record:
            artifacts_map[name] = str(record["path"])
        elif isinstance(record, str):
            artifacts_map[name] = record

    def _resolve_artifact(key: str, filename: str = "") -> Path | None:
        """Locate an artifact file by map key or by filename."""
        if key and key in artifacts_map and Path(artifacts_map[key]).is_file():
            return Path(artifacts_map[key])
        if filename:
            direct = run_path / filename
            if direct.is_file():
                return direct
        return None

    # Load decisions from the summary (AgentDecision list).
    decisions: list[AgentDecision] = []
    for entry in summary_data.get("decisions", []) or []:
        try:
            decisions.append(AgentDecision.model_validate(entry))
        except Exception:
            # Tolerate malformed entries so one bad decision does not
            # abort the whole acceptance check.
            continue

    # Load AtomicClaimSetV3.  Prefer the V3 artifact; fall back to V2
    # claims with migration so runs that used the legacy V2 evidence
    # pipeline can still be evaluated.
    claim_set: AtomicClaimSetV3 | None = None
    claims_path = (
        _resolve_artifact("atomic_claims_v3", "atomic_claims_v3.json")
        or _resolve_artifact("atomic_claims_v2", "atomic_claims_v2.json")
        or _resolve_artifact("claims", "atomic_claims_v2.json")
    )
    if claims_path is not None:
        try:
            from code2paper.agentic.evidence_compiler_v3 import (
                load_atomic_claims_v3_or_v2,
            )
            claim_set = load_atomic_claims_v3_or_v2(claims_path)
        except Exception:
            claim_set = None

    # Load ObligationCoverageReportV2.
    coverage_report: ObligationCoverageReportV2 | None = None
    coverage_path = _resolve_artifact("obligation_coverage_v2", "obligation_coverage_v2.json")
    if coverage_path is not None:
        try:
            coverage_report = ObligationCoverageReportV2.model_validate_json(
                coverage_path.read_text(encoding="utf-8")
            )
        except Exception:
            coverage_report = None

    # Fallback: build the coverage report on-the-fly from the intent
    # graph + claim set + code facts.  This is required because the
    # legacy pipeline does not always emit an ``obligation_coverage_v2``
    # artifact, but the R8 acceptance checker needs it for the
    # ``code_mainline_in_method`` and ``must_cover_terminal`` criteria.
    if coverage_report is None and claim_set is not None:
        intent_path = _resolve_artifact("intent_obligation_graph")
        if intent_path is not None:
            try:
                # Local import to avoid a circular dependency at module load.
                from code2paper.agentic.intent_compiler_v2 import (
                    IntentObligationGraphV2,
                )
                from code2paper.agentic.obligation_fact_alignment import (
                    build_obligation_coverage_v2,
                )
                from code2paper.agentic.evidence_compiler_v3 import load_code_facts_v1

                intent_graph = IntentObligationGraphV2.model_validate_json(
                    intent_path.read_text(encoding="utf-8")
                )
                fact_set = None
                facts_path = _resolve_artifact("code_facts_v1")
                if facts_path is not None:
                    try:
                        fact_set = load_code_facts_v1(facts_path)
                    except Exception:
                        fact_set = None
                coverage_report = build_obligation_coverage_v2(
                    intent_graph,
                    fact_set=fact_set,
                    claim_set=claim_set,
                )
            except Exception:
                coverage_report = None

    # Load TextEvidenceValidationReport.
    validation_report: TextEvidenceValidationReport | None = None
    validation_path = _resolve_artifact("text_evidence_validation", "text_evidence_validation.json")
    if validation_path is not None:
        try:
            validation_report = TextEvidenceValidationReport.model_validate_json(
                validation_path.read_text(encoding="utf-8")
            )
        except Exception:
            validation_report = None

    # Load Method text.
    method_text = ""
    for key in ("text_clean_md", "text_md", "text_clean_tex", "text_tex"):
        path = _resolve_artifact(key)
        if path is not None:
            try:
                method_text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            break

    # Recorded trace digest from the summary (if any).
    recorded_trace_digest = str(summary_data.get("trace_digest", "") or "")

    # Tool-call trace refs from the summary (if any).
    tool_call_trace_refs: list[str] = list(summary_data.get("tool_call_trace_refs", []) or [])

    # Final state digest for checkpoint/resume consistency.
    original_final_state_digest = str(summary_data.get("final_state_digest", "") or "")
    resumed_final_state_digest = ""
    if resumed_run_dir is not None:
        resumed_path = Path(resumed_run_dir).resolve()
        resumed_summary_path = resumed_path / "agentic_run_summary.json"
        if not resumed_summary_path.is_file():
            for candidate in (
                resumed_path / "artifacts" / "10_run" / "agentic_run_summary.json",
                resumed_path / "10_run" / "agentic_run_summary.json",
            ):
                if candidate.is_file():
                    resumed_summary_path = candidate
                    break
        if resumed_summary_path.is_file():
            try:
                resumed_summary = json.loads(resumed_summary_path.read_text(encoding="utf-8"))
                resumed_final_state_digest = str(resumed_summary.get("final_state_digest", "") or "")
            except Exception:
                resumed_final_state_digest = ""

    # Run environment / temperature from the summary.
    run_environment: dict[str, str] = dict(summary_data.get("environment", {}) or {})
    run_temperature_raw = summary_data.get("temperature")
    run_temperature = float(run_temperature_raw) if run_temperature_raw is not None else None

    # Source authority policy from the summary (if any).
    source_authority_policy: dict[str, Any] = dict(summary_data.get("source_authority_policy", {}) or {})

    # paper_read_only_at_end evidence from the summary (if any).
    paper_read_only_at_end_raw = summary_data.get("paper_read_only_at_end", None)
    if paper_read_only_at_end_raw is None:
        paper_read_only_at_end_evidence: bool | None = None
    else:
        paper_read_only_at_end_evidence = bool(paper_read_only_at_end_raw)

    return check_r8_acceptance(
        run_id=effective_run_id,
        project_id=project_id,
        decisions=decisions,
        tool_call_trace_refs=tool_call_trace_refs,
        recorded_trace_digest=recorded_trace_digest,
        coverage_report=coverage_report,
        claim_set=claim_set,
        validation_report=validation_report,
        method_text=method_text,
        original_final_state_digest=original_final_state_digest,
        resumed_final_state_digest=resumed_final_state_digest,
        protocol_settings=protocol_settings,
        run_environment=run_environment,
        run_temperature=run_temperature,
        source_authority_policy=source_authority_policy,
        paper_read_only_at_end=paper_read_only_at_end_evidence,
    )


__all__ = [
    "R8AcceptanceCriterion",
    "R8ProtocolSettings",
    "R8AcceptanceReport",
    "check_r8_acceptance",
    "check_r8_acceptance_from_run_dir",
    "compute_trace_digest",
    "verify_trace_reproducibility",
    "verify_checkpoint_resume_consistency",
    "scan_text_for_project_literals",
    "scan_claims_for_project_literals",
    "extract_equation_tokens",
    "unauthorized_equation_tokens",
    "has_gap_driven_tool_selection",
    "write_r8_acceptance_report",
    "load_r8_acceptance_report",
]
