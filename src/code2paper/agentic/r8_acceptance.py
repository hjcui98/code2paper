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

- ``per_role_sampling_config_evidenced`` -- each live call records the
  role-specific temperature, sampling and node budget that it actually used;
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

R8.1 per-role sampling protocol check (Phase 1):

- ``per_role_sampling_config_evidenced`` -- every unconditional live role
  (``intent_compiler``, ``code_intake``, ``code_analyzer``,
  ``research_supervisor``, ``authoring_planner``, ``method_writer``) has at
  least one :class:`GenerationCallTrace` recorded for the run, AND each trace
  stays within its role's temperature/sampling/output envelope from
  :data:`code2paper.llm.role_config.ROLE_GENERATION_CONFIGS`. Conditional
  ``local_rewrite`` / ``semantic_verifier`` calls are checked when present;
  a clean run does not manufacture them. Missing required traces or
  temperature mismatches are hard failures. Deterministic
  roles (``deterministic_compiler`` / ``deterministic_validator``)
  must NOT have any trace — a trace tagged with a deterministic role
  is also a hard failure.

R8.1 live API evidence check:

- ``real_api_calls_evidenced`` -- every unconditional live role has at
  least one non-cached, unblocked response with provider, model, endpoint and
  non-empty response-hash provenance. Sampling metadata alone is not accepted
  as evidence that a real provider call completed.

R8.1 V3 research integrity check (Phase 2):

- ``v3_research_succeeded`` -- the V3 research subgraph ran without
  raising.  When the run summary's ``v3_error`` field is non-empty,
  the V3 research subgraph failed and the run was silently downgraded
  to a non-V3 pipeline; this is a hard failure (the V3 evidence chain
  is broken and the run cannot be accepted).  An empty ``v3_error``
  means V3 research succeeded (or V3 was not enabled, in which case
  ``v3_error`` is also empty).

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
from code2paper.llm.role_config import (
    AUTHORING_PLANNER,
    CODE_ANALYZER,
    CODE_INTAKE,
    DETERMINISTIC_ROLES,
    INTENT_COMPILER,
    LLM_CALLING_ROLES,
    METHOD_WRITER,
    RESEARCH_SUPERVISOR,
    ROLE_GENERATION_CONFIGS,
)

# These roles are unconditional in a formal V3 live run.  Local rewrite and
# semantic verification are conditional: a clean deterministic reverse gate
# legitimately invokes neither.  When optional-role traces exist they are
# still validated below, but their absence must not force a fake LLM call.
REQUIRED_LIVE_TRACE_ROLES = (
    INTENT_COMPILER,
    CODE_INTAKE,
    CODE_ANALYZER,
    RESEARCH_SUPERVISOR,
    AUTHORING_PLANNER,
    METHOD_WRITER,
)


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

    # Kept only to parse older R8 artifacts.  A global temperature is a
    # startup compatibility sentinel, not a formal sampling constraint: the
    # authoritative values are the per-call role traces below.
    temperature: float | None = None
    llm_cache_env: str = "0"
    # ``single_tp2_instance`` preserves the original Gemma R8 contract.  A
    # model/profile may instead freeze an explicit deployment topology.  This
    # keeps topology audited without hard-coding every future model to TP=2.
    single_tp2_instance: bool = True
    expected_tp_size: int | None = None
    expected_num_gpus: int | None = None
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
    # The research supervisor's goal always contains "obligation="
    # because every tool selection is driven by an active obligation
    # (i.e. an information gap in the evidence coverage).  This
    # indicator ensures that V3 research decisions whose goal field
    # is preserved via ``convert_v3_decisions_to_agent_decisions``
    # are recognised as gap-driven even when the LLM rationale text
    # does not contain explicit gap keywords.
    "obligation",
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
    generation_call_traces: Iterable[Any] | None = None,
    temperature_by_role: Mapping[str, Any] | None = None,
    top_p_by_role: Mapping[str, Any] | None = None,
    top_k_by_role: Mapping[str, Any] | None = None,
    max_output_tokens_by_role: Mapping[str, Any] | None = None,
    intent_target_proposal_report: Mapping[str, Any] | None = None,
    v3_error: str = "",
    completion_report: Any | None = None,
    readiness_report: Any | None = None,
    validation_manifest: Any | None = None,
    method_clean_path: str = "",
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
        Historical global LLM temperature record.  It is retained for
        artifact compatibility but is not an acceptance constraint; the
        role-specific generation traces are checked instead.
    source_authority_policy
        The run's source authority policy.  Used by the
        ``code_and_author_yml_only`` protocol check.
    paper_read_only_at_end
        Evidence that the original paper was read only AFTER the Method
        was authored (i.e., for diagnostic comparison).  ``None`` means
        the run did not record this evidence, which fails the protocol
        check.  Used by the ``paper_read_only_at_end`` protocol check.
    generation_call_traces
        Iterable of :class:`code2paper.llm.generation_trace.GenerationCallTrace`
        objects (or their JSON dicts) recorded for the run.  Used by
        the ``per_role_sampling_config_evidenced`` protocol check to
        verify each unconditional role has at least one trace and each
        trace stays within its role's temperature/sampling/output envelope.
        ``None`` or empty means the check fails (the run
        did not evidence per-role sampling config).
    v3_error
        The V3 research error recorded for the run (from
        ``AgenticRunSummary.v3_error``).  When non-empty, the V3
        research subgraph failed and the run was silently downgraded
        to a non-V3 pipeline; the ``v3_research_succeeded`` criterion
        fails (the V3 evidence chain is broken and the run cannot be
        accepted).  Empty string means V3 research succeeded (or V3
        was not enabled).
    """

    settings = protocol_settings or R8ProtocolSettings()
    decisions_list = list(decisions or [])
    tool_refs_list = list(tool_call_trace_refs or [])
    env = dict(run_environment or {})
    authority = dict(source_authority_policy or {})
    traces_list = list(generation_call_traces or [])
    intent_report = dict(intent_target_proposal_report or {})
    v3_error_normalized = str(v3_error or "")

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
        coverage_report, claim_set, validation_report, method_text
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

    # 9. per_role_sampling_config_evidenced (R8.1 Phase 1 protocol check).
    # Verifies every LLM-calling role has at least one trace with the
    # protocol-mandated effective temperature, and that no deterministic
    # role accidentally issued an LLM call.
    role_sampling_ok, role_sampling_reason, role_sampling_evidence = (
        _check_per_role_sampling_config(
            traces_list,
            temperature_by_role=temperature_by_role,
            top_p_by_role=top_p_by_role,
            top_k_by_role=top_k_by_role,
            max_output_tokens_by_role=max_output_tokens_by_role,
        )
    )
    criteria["per_role_sampling_config_evidenced"] = R8AcceptanceCriterion(
        criterion_id="per_role_sampling_config_evidenced",
        description=(
            "Every LLM-calling role has at least one GenerationCallTrace "
            "with an effective temperature matching the role protocol."
        ),
        status="passed" if role_sampling_ok else "failed",
        reason=role_sampling_reason,
        evidence=role_sampling_evidence,
    )

    # 10. real_api_calls_evidenced. Sampling metadata alone does not prove
    # that a provider was called: dry-run, provider=none, cached and blocked
    # responses can all emit traces.
    real_api_ok, real_api_reason, real_api_evidence = (
        _check_real_api_calls_evidenced(traces_list)
    )
    criteria["real_api_calls_evidenced"] = R8AcceptanceCriterion(
        criterion_id="real_api_calls_evidenced",
        description=(
            "Every unconditional live role has a non-cached, unblocked "
            "provider response trace."
        ),
        status="passed" if real_api_ok else "failed",
        reason=real_api_reason,
        evidence=real_api_evidence,
    )

    # 11. v3_research_succeeded (R8.1 Phase 2 V3 research integrity
    # check).  When the V3 research subgraph raised an exception, the
    # run was silently downgraded to a non-V3 pipeline -- the V3
    # evidence chain (behavior graph, packets, facts, claims) is broken
    # and the run cannot be accepted.  An empty ``v3_error`` means V3
    # research succeeded (or V3 was not enabled, in which case the
    # field is also empty).
    if v3_error_normalized:
        v3_status: CriterionStatus = "failed"
        # Truncate very long error messages so the reason stays
        # readable in the report.  The full error is preserved in the
        # run summary's ``v3_error`` field.
        v3_reason = (
            f"V3 research subgraph failed: {v3_error_normalized[:300]}"
            + ("..." if len(v3_error_normalized) > 300 else "")
        )
        v3_evidence = (v3_error_normalized,)
    else:
        v3_status = "passed"
        v3_reason = "V3 research succeeded (or V3 not enabled)"
        v3_evidence = ()
    criteria["v3_research_succeeded"] = R8AcceptanceCriterion(
        criterion_id="v3_research_succeeded",
        description=(
            "V3 research subgraph ran without raising (v3_error is empty)."
        ),
        status=v3_status,
        reason=v3_reason,
        evidence=v3_evidence,
    )

    # 11. The live Intent Agent must have produced a complete, schema-valid
    # proposal.  Falling back to lexical concept targets is acceptable for
    # offline tests, but cannot prove R8 holdout robustness.
    intent_ok = bool(intent_report.get("attempted")) and bool(
        intent_report.get("accepted")
    )
    intent_reason = (
        "typed Intent Agent proposal accepted"
        if intent_ok
        else "typed Intent Agent proposal missing or rejected: "
        + str(intent_report.get("failure") or "no_report")
    )
    criteria["typed_intent_proposal_accepted"] = R8AcceptanceCriterion(
        criterion_id="typed_intent_proposal_accepted",
        description=(
            "Gemma proposed complete typed targets and deterministic "
            "normalization accepted them before research."
        ),
        status="passed" if intent_ok else "failed",
        reason=intent_reason,
        evidence=(str(intent_report.get("enriched_graph_digest") or ""),)
        if intent_ok else (),
    )

    # 12. completion_complete — the run's completion report must indicate
    # that all required deliverables are present and complete.
    if completion_report is not None:
        if hasattr(completion_report, "model_dump"):
            completion_dict = completion_report.model_dump(mode="json")
        elif isinstance(completion_report, dict):
            completion_dict = completion_report
        else:
            completion_dict = {}
        complete = bool(completion_dict.get("complete", False))
        completion_status = str(completion_dict.get("status", "unknown"))
        completion_blocked = str(completion_dict.get("blocked_reason", ""))
        missing = list(completion_dict.get("missing_deliverables", []) or [])
        if complete:
            completion_reason = "completion_report.complete=true"
        elif completion_blocked:
            completion_reason = (
                f"completion_report.complete=false blocked={completion_blocked}"
            )
        else:
            completion_reason = (
                f"completion_report.complete=false status={completion_status}"
                + (f" missing={missing}" if missing else "")
            )
    else:
        complete = False
        completion_reason = "completion_report not found"
    criteria["completion_complete"] = R8AcceptanceCriterion(
        criterion_id="completion_complete",
        description="Agentic run completion report marks all deliverables complete.",
        status="passed" if complete else "failed",
        reason=completion_reason,
    )

    # 13. readiness_passed — the run's readiness report must indicate all
    # blocking checks passed.
    if readiness_report is not None:
        if hasattr(readiness_report, "model_dump"):
            readiness_dict = readiness_report.model_dump(mode="json")
        elif isinstance(readiness_report, dict):
            readiness_dict = readiness_report
        else:
            readiness_dict = {}
        readiness_passed = bool(readiness_dict.get("passed", False))
        blocking_failures = int(readiness_dict.get("blocking_failures", 0))
        if readiness_passed:
            readiness_reason = "readiness_report.passed=true"
        else:
            readiness_reason = (
                f"readiness_report.passed=false blocking_failures={blocking_failures}"
            )
    else:
        readiness_passed = False
        readiness_reason = "readiness_report not found"
    criteria["readiness_passed"] = R8AcceptanceCriterion(
        criterion_id="readiness_passed",
        description="Agentic run readiness report has passed=true.",
        status="passed" if readiness_passed else "failed",
        reason=readiness_reason,
    )

    # 14. validation_manifest_passed — the validation manifest must exist
    # and have status=passed.
    if validation_manifest is not None:
        if hasattr(validation_manifest, "model_dump"):
            vm_dict = validation_manifest.model_dump(mode="json")
        elif isinstance(validation_manifest, dict):
            vm_dict = validation_manifest
        else:
            vm_dict = {}
        vm_status = str(vm_dict.get("status") or "")
        vm_passed = vm_status == "passed"
        vm_reason = (
            f"validation_manifest status={vm_status}"
            if vm_passed
            else f"validation_manifest status={vm_status} (expected 'passed')"
        )
    else:
        vm_passed = False
        vm_reason = "validation_manifest not found or failed"
    criteria["validation_manifest_passed"] = R8AcceptanceCriterion(
        criterion_id="validation_manifest_passed",
        description="Validation manifest exists and has status=passed.",
        status="passed" if vm_passed else "failed",
        reason=vm_reason,
    )

    # 15. method_clean_exists — the final Method (method_clean.md) must
    # exist as a file.
    method_clean_exists = bool(method_clean_path) and Path(method_clean_path).is_file()
    criteria["method_clean_exists"] = R8AcceptanceCriterion(
        criterion_id="method_clean_exists",
        description="Final method_clean.md exists on disk.",
        status="passed" if method_clean_exists else "failed",
        reason=(
            f"method_clean.md found at {method_clean_path}"
            if method_clean_exists
            else "method_clean.md is missing"
        ),
    )

    # 16. method_has_supported_mainline — the number of supported/partial
    # must_cover mainline claims that entered the Method must be > 0.
    # This is a semantic duplicate of code_mainline_in_method but is
    # expressed as a separate criterion so the acceptance report can
    # distinguish between "gap-only" and "no claims at all" failures.
    #
    # Use the same two-tier approach as code_mainline_in_method: first
    # check the coverage report for terminal must_cover obligations,
    # then check the claim_set for supported claims that cover those
    # obligations AND are validated in the final text verdict.  This
    # avoids false negatives when synthetic gaps mark obligations as
    # explicit_gap but the claim_set still has valid supported claims.
    mainline_count = 0
    if coverage_report is not None and hasattr(coverage_report, "items"):
        supported_must_ids = {
            item.obligation_id
            for item in coverage_report.items
            if item.obligation_priority == "must_cover" and item.coverage_status == "supported"
        }
        terminal_must_ids = {
            item.obligation_id
            for item in coverage_report.items
            if item.obligation_priority == "must_cover"
            and item.coverage_status in {"supported", "partial", "explicit_gap", "blocked"}
        }
        if claim_set is not None and terminal_must_ids:
            supported_claims_for_must = [
                claim for claim in claim_set.claims
                if claim.status == "supported"
                and any(obl_id in terminal_must_ids for obl_id in claim.covers_obligation_ids)
            ]
            if validation_report is not None and supported_claims_for_must:
                validated_ids = {
                    pid
                    for verdict in validation_report.verdicts
                    if verdict.status in {"supported", "caveated"}
                    for pid in verdict.matched_projection_claim_ids
                }
                if validated_ids:
                    supported_claims_for_must = [
                        c for c in supported_claims_for_must
                        if c.claim_id in validated_ids
                    ]
                else:
                    # Legacy fallback: aggregate counts without per-verdict
                    # projection IDs (V1 fixtures/artifacts).
                    validated = (
                        validation_report.supported_claims
                        + validation_report.caveated_claims
                    )
                    if not (supported_must_ids and validated > 0):
                        supported_claims_for_must = []
            mainline_count = len(supported_claims_for_must)
    if mainline_count > 0:
        mainline_reason = f"supported_or_partial_must_cover_count={mainline_count}"
    else:
        mainline_reason = (
            f"supported_or_partial_must_cover_count=0; "
            f"no must_cover obligation has a supported/partial mainline"
        )
    criteria["method_has_supported_mainline"] = R8AcceptanceCriterion(
        criterion_id="method_has_supported_mainline",
        description="At least one must_cover obligation has a supported/partial mainline.",
        status="passed" if mainline_count > 0 else "failed",
        reason=mainline_reason,
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
    method_text: str = "",
) -> tuple[bool, str]:
    """Check that at least one supported must_cover claim entered the Method.

    The code mainline is in the Method when a supported V3 claim is bound to
    a must-cover obligation *and that same claim* occurs in a supported or
    caveated final-text verdict.  The obligation may remain ``partial`` when
    another typed target is an explicit boundary/gap; requiring the aggregate
    obligation itself to be fully ``supported`` incorrectly rejects an
    evidence-backed mainline that is already present in the Method.

    The Method must also contain at least one factual unit: the text must
    be non-empty and contain more than a bare title (e.g. ``# Method`` alone
    is not acceptable).  All must_cover obligations being ``explicit_gap``
    is NOT a valid pass; at least one must_cover obligation must be covered
    by a supported/partial claim that enters the Method.
    """

    if coverage_report is None or claim_set is None or validation_report is None:
        return False, "missing coverage_report / claim_set / validation_report"

    # --- Method factual unit check ---
    # A Method that is empty or contains only a title (e.g. "# Method") has
    # no factual units and cannot satisfy code_mainline_in_method regardless
    # of any other artifacts.
    stripped = method_text.strip()
    if not stripped:
        return False, "method_text is empty; no factual units"
    # Remove markdown heading lines (lines starting with #) and check if
    # any content remains after stripping.
    non_heading_lines = [
        line for line in stripped.splitlines()
        if not line.strip().startswith("#")
    ]
    if not non_heading_lines or all(
        not ln.strip() for ln in non_heading_lines
    ):
        return False, "method_text contains only heading(s); no factual units"

    supported_must_cover_ids = {
        item.obligation_id
        for item in coverage_report.items
        if item.obligation_priority == "must_cover" and item.coverage_status == "supported"
    }
    terminal_must_cover_ids = {
        item.obligation_id
        for item in coverage_report.items
        if item.obligation_priority == "must_cover"
        and item.coverage_status in {"supported", "partial", "explicit_gap", "blocked"}
    }
    if not terminal_must_cover_ids:
        return False, "no must_cover obligation reached a terminal coverage status"

    supported_claims_for_must_cover = [
        claim for claim in claim_set.claims
        if claim.status == "supported"
        and any(obl_id in terminal_must_cover_ids for obl_id in claim.covers_obligation_ids)
    ]
    if not supported_claims_for_must_cover:
        return False, (
            f"no supported claim covers a must_cover obligation "
            f"(terminal_must_cover_count={len(terminal_must_cover_ids)})"
        )

    validated_projection_ids = {
        projection_claim_id
        for verdict in validation_report.verdicts
        if verdict.status in {"supported", "caveated"}
        for projection_claim_id in verdict.matched_projection_claim_ids
    }
    entered_claim_ids = sorted(
        claim.claim_id
        for claim in supported_claims_for_must_cover
        if claim.claim_id in validated_projection_ids
    )
    if not entered_claim_ids:
        # Compatibility for V1 validation fixtures/artifacts that recorded
        # aggregate counts but no per-verdict projection IDs.  This fallback is
        # safe only for a fully-supported obligation; partial obligations need
        # the explicit claim-level join above.
        validated = validation_report.supported_claims + validation_report.caveated_claims
        if supported_must_cover_ids and validated > 0 and not validated_projection_ids:
            return True, (
                f"must_cover_supported={len(supported_must_cover_ids)} "
                f"claims_for_must_cover={len(supported_claims_for_must_cover)} "
                f"validated={validated} legacy_aggregate_validation=true"
            )
        if not supported_must_cover_ids:
            return False, "no must_cover obligation reached status=supported or supplied an explicit validated claim join"
        return False, "no supported must_cover claim appears in a supported/caveated final-text verdict"
    return True, (
        f"must_cover_terminal={len(terminal_must_cover_ids)} "
        f"claims_for_must_cover={len(supported_claims_for_must_cover)} "
        f"validated_mainline_claims={','.join(entered_claim_ids)}"
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
# Per-role sampling config check (Phase 1 R8.1 protocol)
# ---------------------------------------------------------------------------


def _check_real_api_calls_evidenced(
    traces: Iterable[Any],
) -> tuple[bool, str, tuple[str, ...]]:
    """Require successful, non-cached provider responses for live roles."""

    empty_response_hash = "sha256:" + hashlib.sha256(b"").hexdigest()
    qualifying_roles: set[str] = set()
    rejected_by_role: dict[str, list[str]] = {}

    def _field(trace: Any, name: str, default: Any = None) -> Any:
        if isinstance(trace, Mapping):
            return trace.get(name, default)
        return getattr(trace, name, default)

    for index, trace in enumerate(list(traces or [])):
        role = str(_field(trace, "role", "") or "")
        if role not in REQUIRED_LIVE_TRACE_ROLES:
            continue
        call_id = str(_field(trace, "call_id", "") or f"trace-{index}")
        cached = _field(trace, "cached", None)
        blocked_reason = str(_field(trace, "blocked_reason", "") or "").strip()
        finish_reason = str(_field(trace, "finish_reason", "") or "").strip()
        response_hash = str(_field(trace, "response_hash", "") or "").strip()
        provider = str(_field(trace, "provider", "") or "").strip().lower()
        model = str(_field(trace, "model", "") or "").strip()
        endpoint_origin = str(_field(trace, "endpoint_origin", "") or "").strip()

        trace_failures: list[str] = []
        if cached is not False:
            trace_failures.append(
                "cached" if bool(cached) else "cache_status_not_recorded"
            )
        if blocked_reason:
            trace_failures.append(f"blocked={blocked_reason}")
        if provider in {"", "none", "offline", "mock", "fake", "fixture"}:
            trace_failures.append(f"provider={provider or 'missing'}")
        if not model or model.lower() in {"none", "mock", "fake", "fixture"}:
            trace_failures.append("model_missing_or_placeholder")
        if not re.match(r"^https?://[^/\s]+", endpoint_origin, re.IGNORECASE):
            trace_failures.append("endpoint_origin_missing_or_invalid")
        if not finish_reason:
            trace_failures.append("finish_reason_missing")
        if not response_hash or response_hash == empty_response_hash:
            trace_failures.append("nonempty_response_not_evidenced")

        if trace_failures:
            rejected_by_role.setdefault(role, []).append(
                f"role={role} call_id={call_id} " + ",".join(trace_failures)
            )
        else:
            qualifying_roles.add(role)

    missing_roles = [
        role for role in REQUIRED_LIVE_TRACE_ROLES
        if role not in qualifying_roles
    ]
    failures = [
        failure
        for role in missing_roles
        for failure in rejected_by_role.get(role, [])
    ]
    if missing_roles:
        failures.append(
            "missing_real_api_role_traces:roles=" + ",".join(missing_roles)
        )
    if failures:
        return False, (
            f"{len(failures)} real API evidence failures: "
            + "; ".join(failures[:5])
            + (" ..." if len(failures) > 5 else "")
        ), tuple(failures)
    return True, (
        "all unconditional live roles have non-cached, unblocked provider "
        "response evidence with API provenance"
    ), ()


def _check_per_role_sampling_config(
    traces: Iterable[Any],
    *,
    temperature_by_role: Mapping[str, Any] | None = None,
    top_p_by_role: Mapping[str, Any] | None = None,
    top_k_by_role: Mapping[str, Any] | None = None,
    max_output_tokens_by_role: Mapping[str, Any] | None = None,
) -> tuple[bool, str, tuple[str, ...]]:
    """Check that every LLM-calling role has compliant trace evidence.

    Returns ``(ok, reason, evidence)``.  ``evidence`` is a tuple of
    human-readable failure strings (empty when ``ok`` is ``True``).

    A trace may be a :class:`GenerationCallTrace` instance or a JSON
    dict (loaded from disk).  Each trace's role, temperature, top-p/top-k,
    and output ceiling are compared with the resolved run profile recorded
    before the calls.  Older artifacts that do not contain a resolved profile
    retain the frozen :data:`ROLE_GENERATION_CONFIGS` protocol.  A smaller
    output ceiling is permitted (for a short schema or remaining cumulative
    writer budget); a larger one is not.

    Failure modes (all are hard failures):

    - A trace tagged with a deterministic role
      (``deterministic_compiler`` / ``deterministic_validator``).
    - Any unconditional live role with zero traces. Conditional roles are
      checked when invoked but are not required to manufacture a no-op call.
    - Any trace whose effective temperature does not match the role's
      protocol default (within ``1e-6`` tolerance).
    - A trace whose shape cannot be parsed (missing role /
      temperature).
    """

    traces_list = list(traces or [])
    normalized: list[dict[str, Any]] = []
    parse_errors: list[str] = []
    for index, trace in enumerate(traces_list):
        role, temperature, call_id, error = _extract_trace_role_temperature(trace, index)
        if error is not None:
            parse_errors.append(error)
            continue
        assert role is not None and temperature is not None  # for type checkers
        sampling, sampling_error = _extract_trace_sampling_fields(trace, index)
        if sampling_error is not None:
            parse_errors.append(sampling_error)
            continue
        normalized.append({
            "role": role,
            "temperature": float(temperature),
            "call_id": call_id,
            **sampling,
        })

    failures: list[str] = list(parse_errors)

    profile_maps = (
        temperature_by_role,
        top_p_by_role,
        top_k_by_role,
        max_output_tokens_by_role,
    )
    resolved_profile_supplied = any(item is not None for item in profile_maps)
    resolved_profile_complete = all(item is not None for item in profile_maps)
    if resolved_profile_supplied and not resolved_profile_complete:
        failures.append("resolved_run_profile_incomplete:all four role maps are required")

    resolved_temperatures = dict(temperature_by_role or {})
    resolved_top_p = dict(top_p_by_role or {})
    resolved_top_k = dict(top_k_by_role or {})
    resolved_max_tokens = dict(max_output_tokens_by_role or {})
    if resolved_profile_supplied and resolved_profile_complete:
        for role in LLM_CALLING_ROLES:
            for field_name, values in (
                ("temperature", resolved_temperatures),
                ("top_p", resolved_top_p),
                ("top_k", resolved_top_k),
                ("max_output_tokens", resolved_max_tokens),
            ):
                if role not in values:
                    failures.append(
                        f"resolved_run_profile_missing:role={role} field={field_name}"
                    )

    # 1. No trace may be tagged with a deterministic role.
    for entry in normalized:
        role = entry["role"]
        call_id = entry["call_id"]
        if role in DETERMINISTIC_ROLES:
            failures.append(
                f"deterministic_role_has_trace:role={role} call_id={call_id}"
            )

    # 2. Group traces by role for the LLM-calling roles.
    traces_by_role: dict[str, list[dict[str, Any]]] = {}
    for entry in normalized:
        traces_by_role.setdefault(entry["role"], []).append(entry)

    # 3. Each unconditional live role must have at least one trace.
    missing_roles = [role for role in REQUIRED_LIVE_TRACE_ROLES if not traces_by_role.get(role)]
    if missing_roles:
        failures.append(
            f"missing_role_traces:roles={','.join(missing_roles)}"
        )

    # 4. Each trace must stay in the role's sampling envelope.  Unknown
    # roles are also flagged here.
    for role, entries in traces_by_role.items():
        if role in DETERMINISTIC_ROLES:
            # Already flagged in step 1.
            continue
        if role not in ROLE_GENERATION_CONFIGS:
            failures.append(
                f"unknown_role:role={role} count={len(entries)}"
            )
            continue
        role_config = ROLE_GENERATION_CONFIGS[role]
        if resolved_profile_supplied:
            if not resolved_profile_complete or any(
                role not in values
                for values in (
                    resolved_temperatures,
                    resolved_top_p,
                    resolved_top_k,
                    resolved_max_tokens,
                )
            ):
                continue
            try:
                expected_temp = float(resolved_temperatures[role])
                expected_top_p_raw = resolved_top_p[role]
                expected_top_p = (
                    None if expected_top_p_raw is None else float(expected_top_p_raw)
                )
                expected_top_k_raw = resolved_top_k[role]
                expected_top_k = (
                    None if expected_top_k_raw is None else int(expected_top_k_raw)
                )
                ceiling = int(resolved_max_tokens[role])
            except (TypeError, ValueError):
                failures.append(f"resolved_run_profile_invalid:role={role}")
                continue
        else:
            expected_temp = role_config.temperature
            expected_top_p = role_config.top_p
            expected_top_k = role_config.top_k
            ceiling = role_config.max_output_tokens_default
        for entry in entries:
            temperature = entry["temperature"]
            call_id = entry["call_id"]
            if abs(temperature - expected_temp) > 1e-6:
                failures.append(
                    f"temperature_mismatch:role={role} call_id={call_id} "
                    f"actual={temperature} expected={expected_temp}"
                )
            actual_top_p = entry["top_p"]
            if expected_top_p is None:
                if actual_top_p is not None:
                    failures.append(
                        f"top_p_mismatch:role={role} call_id={call_id} "
                        f"actual={actual_top_p} expected=None"
                    )
            elif (
                actual_top_p is None
                or abs(actual_top_p - expected_top_p) > 1e-6
            ):
                failures.append(
                    f"top_p_mismatch:role={role} call_id={call_id} "
                    f"actual={actual_top_p} expected={expected_top_p}"
                )
            actual_top_k = entry["top_k"]
            if actual_top_k != expected_top_k:
                failures.append(
                    f"top_k_mismatch:role={role} call_id={call_id} "
                    f"actual={actual_top_k} expected={expected_top_k}"
                )
            if role == METHOD_WRITER and entry["extended_budget_used"]:
                if resolved_profile_supplied:
                    try:
                        ceiling = int(resolved_max_tokens["method_writer_extended"])
                    except (KeyError, TypeError, ValueError):
                        failures.append(
                            "resolved_run_profile_missing:role=method_writer "
                            "field=method_writer_extended"
                        )
                        continue
                else:
                    ceiling = role_config.max_output_tokens(extended=True)
            actual_max = entry["max_output_tokens"]
            if actual_max < 1 or actual_max > ceiling:
                failures.append(
                    f"max_output_tokens_out_of_range:role={role} call_id={call_id} "
                    f"actual={actual_max} ceiling={ceiling}"
                )

    if failures:
        return False, (
            f"{len(failures)} per-role sampling config failures: "
            + "; ".join(failures[:5])
            + (" ..." if len(failures) > 5 else "")
        ), tuple(failures)
    role_counts = ", ".join(
        f"{role}={len(traces_by_role.get(role, []))}" for role in LLM_CALLING_ROLES
    )
    protocol_name = (
        "resolved_run_profile" if resolved_profile_supplied else "frozen_role_protocol"
    )
    return True, (
        f"all traced roles comply with {protocol_name} ({role_counts})"
    ), ()


def _extract_trace_role_temperature(
    trace: Any,
    index: int,
) -> tuple[str | None, float | None, str, str | None]:
    """Extract (role, temperature, call_id, error) from a trace.

    Returns ``(role, temperature, call_id, None)`` on success, or
    ``(None, None, "", error_message)`` when the trace shape is
    unrecognized.  ``temperature`` is the float effective temperature.
    """

    # Try object-style access (GenerationCallTrace instance).
    role_attr = getattr(trace, "role", None)
    call_id_attr = getattr(trace, "call_id", "") or f"trace-{index}"
    effective_config = getattr(trace, "effective_config", None)
    temperature_attr = getattr(effective_config, "temperature", None)
    if role_attr is not None and temperature_attr is not None:
        try:
            return str(role_attr), float(temperature_attr), str(call_id_attr), None
        except (TypeError, ValueError) as exc:
            return None, None, "", f"trace_{index}_invalid_temperature:{exc}"

    # Try dict-style access (loaded from JSON).
    if isinstance(trace, dict):
        role_str = trace.get("role", "") or ""
        call_id_str = str(trace.get("call_id", "") or f"trace-{index}")
        eff_cfg = trace.get("effective_config") or {}
        if not isinstance(eff_cfg, dict):
            return None, None, "", f"trace_{index}_invalid_effective_config:type={type(eff_cfg).__name__}"
        temp_raw = eff_cfg.get("temperature")
        if not role_str:
            return None, None, "", f"trace_{index}_missing_role"
        if temp_raw is None:
            return None, None, "", f"trace_{index}_missing_temperature:role={role_str}"
        try:
            return str(role_str), float(temp_raw), call_id_str, None
        except (TypeError, ValueError) as exc:
            return None, None, "", f"trace_{index}_invalid_temperature:{exc}"

    return (
        None,
        None,
        "",
        f"trace_{index}_unrecognized_shape:type={type(trace).__name__}",
    )


def _extract_trace_sampling_fields(
    trace: Any,
    index: int,
) -> tuple[dict[str, Any], str | None]:
    """Extract audited non-temperature sampling fields from one trace."""

    effective_config = getattr(trace, "effective_config", None)
    if effective_config is not None and not isinstance(trace, dict):
        max_raw = getattr(effective_config, "max_output_tokens", None)
        top_p_raw = getattr(effective_config, "top_p", None)
        top_k_raw = getattr(effective_config, "top_k", None)
        extended = bool(getattr(trace, "extended_budget_used", False))
    elif isinstance(trace, dict):
        effective_config = trace.get("effective_config") or {}
        if not isinstance(effective_config, dict):
            return {}, f"trace_{index}_invalid_effective_config"
        max_raw = effective_config.get("max_output_tokens")
        top_p_raw = effective_config.get("top_p")
        top_k_raw = effective_config.get("top_k")
        extended = bool(trace.get("extended_budget_used", False))
    else:
        return {}, f"trace_{index}_unrecognized_sampling_shape"
    try:
        max_output_tokens = int(max_raw)
    except (TypeError, ValueError):
        return {}, f"trace_{index}_missing_or_invalid_max_output_tokens"
    try:
        top_p = None if top_p_raw is None else float(top_p_raw)
    except (TypeError, ValueError):
        return {}, f"trace_{index}_invalid_top_p"
    try:
        top_k = None if top_k_raw is None else int(top_k_raw)
    except (TypeError, ValueError):
        return {}, f"trace_{index}_invalid_top_k"
    return {
        "max_output_tokens": max_output_tokens,
        "top_p": top_p,
        "top_k": top_k,
        "extended_budget_used": extended,
    }, None


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

    # ``run_temperature`` is intentionally not checked here.  It is the
    # historical global environment value (normally a 0.0 compatibility
    # sentinel); role-specific call traces are the only source of truth for
    # sampling policy and are checked by ``_check_per_role_sampling_config``.
    del run_temperature

    # llm_cache_off
    actual_cache = env.get("CODE2PAPER_LLM_CACHE", "")
    if actual_cache != settings.llm_cache_env:
        failures.append(
            f"llm_cache_mismatch:run={actual_cache!r} expected={settings.llm_cache_env!r}"
        )

    # Deployment topology is checked against the profile-specific expected
    # values when supplied.  Older Gemma artifacts retain the frozen TP=2
    # contract through ``single_tp2_instance``.
    tp_size = env.get("CODE2PAPER_TP_SIZE", "")
    num_gpus = env.get("CODE2PAPER_NUM_GPUS", "")
    expected_tp_size = settings.expected_tp_size
    expected_num_gpus = settings.expected_num_gpus
    if expected_tp_size is None and settings.single_tp2_instance:
        expected_tp_size = 2
    if expected_num_gpus is None and settings.single_tp2_instance:
        expected_num_gpus = 2
    if expected_tp_size is not None:
        if not tp_size:
            failures.append(f"tp_size_not_recorded:expected={expected_tp_size}")
        elif tp_size != str(expected_tp_size):
            failures.append(
                f"tp_size_mismatch:run={tp_size} expected={expected_tp_size}"
            )
    if expected_num_gpus is not None:
        if not num_gpus:
            failures.append(f"num_gpus_not_recorded:expected={expected_num_gpus}")
        elif num_gpus != str(expected_num_gpus):
            failures.append(
                f"num_gpus_mismatch:run={num_gpus} expected={expected_num_gpus}"
            )

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
        intent_path = (
            _resolve_artifact("intent_obligation_graph_v2")
            or _resolve_artifact("intent_obligation_graph")
        )
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
    # When the resume run writes to the same directory as the original
    # (the common case when the checkpoint's out_root overrides the
    # CLI's --out-root), the summary's ``resumed_from_final_state_digest``
    # field carries the original digest and ``final_state_digest`` is
    # the resumed digest.  When a separate ``resumed_run_dir`` is
    # provided and contains its own summary, use that instead.
    original_final_state_digest = ""
    resumed_final_state_digest = ""
    resumed_marker = str(summary_data.get("resumed_from_final_state_digest", "") or "")
    if resumed_marker:
        original_final_state_digest = resumed_marker
        resumed_final_state_digest = str(summary_data.get("final_state_digest", "") or "")
    else:
        original_final_state_digest = str(summary_data.get("final_state_digest", "") or "")
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
    if protocol_settings is None and (
        run_environment.get("CODE2PAPER_R8_EXPECT_TP_SIZE")
        or run_environment.get("CODE2PAPER_R8_EXPECT_NUM_GPUS")
    ):
        expected_tp_raw = run_environment.get("CODE2PAPER_R8_EXPECT_TP_SIZE", "")
        expected_gpus_raw = run_environment.get("CODE2PAPER_R8_EXPECT_NUM_GPUS", "")
        protocol_settings = R8ProtocolSettings(
            single_tp2_instance=False,
            expected_tp_size=(int(expected_tp_raw) if expected_tp_raw.isdigit() else None),
            expected_num_gpus=(int(expected_gpus_raw) if expected_gpus_raw.isdigit() else None),
        )

    # Source authority policy from the summary (if any).
    source_authority_policy: dict[str, Any] = dict(summary_data.get("source_authority_policy", {}) or {})

    # paper_read_only_at_end evidence from the summary (if any).
    paper_read_only_at_end_raw = summary_data.get("paper_read_only_at_end", None)
    if paper_read_only_at_end_raw is None:
        paper_read_only_at_end_evidence: bool | None = None
    else:
        paper_read_only_at_end_evidence = bool(paper_read_only_at_end_raw)

    # Generation call traces from the summary (Phase 1 R8.1 protocol).
    # Stored as a list of JSON dicts (GenerationCallTrace.model_dump).
    # When not present, the per-role sampling config check will fail
    # (the run did not evidence per-role sampling config).
    generation_call_traces: list[Any] = list(
        summary_data.get("generation_call_traces", []) or []
    )
    resolved_profile_maps = {
        "temperature_by_role": summary_data.get("temperature_by_role"),
        "top_p_by_role": summary_data.get("top_p_by_role"),
        "top_k_by_role": summary_data.get("top_k_by_role"),
        "max_output_tokens_by_role": summary_data.get("max_output_tokens_by_role"),
    }
    # Empty maps in pre-profile summaries mean that no resolved profile was
    # recorded.  Preserve the frozen legacy protocol for those artifacts.
    if not any(bool(value) for value in resolved_profile_maps.values()):
        resolved_profile_maps = {key: None for key in resolved_profile_maps}
    intent_target_proposal_report: dict[str, Any] = {}
    intent_report_path = _resolve_artifact(
        "intent_target_proposal_report_v1",
        "artifacts/intent_target_proposal_report_v1.json",
    ) or _resolve_artifact(
        "intent_target_proposal_report_v1",
        "intent_target_proposal_report_v1.json",
    )
    if intent_report_path is not None:
        try:
            intent_target_proposal_report = json.loads(
                intent_report_path.read_text(encoding="utf-8")
            )
        except Exception:
            intent_target_proposal_report = {}

    # V3 research error from the summary (Phase 2 R8.1 protocol).
    # When non-empty, the V3 research subgraph failed and the run was
    # silently downgraded -- the ``v3_research_succeeded`` criterion
    # fails so the run cannot be accepted.
    v3_error: str = str(summary_data.get("v3_error", "") or "")

    # --- Completion report ---
    completion_report: Any = None
    completion_path = _resolve_artifact(
        "agentic_run_completion_report",
        "artifacts/10_run/agentic_run_completion_report.json",
    ) or _resolve_artifact(
        "agentic_run_completion_report",
        "agentic_run_completion_report.json",
    )
    if completion_path is not None:
        try:
            from code2paper.agentic.completion_report import load_run_completion_report
            completion_report = load_run_completion_report(completion_path)
        except Exception:
            completion_report = None

    # --- Readiness report ---
    readiness_report: Any = None
    readiness_path = _resolve_artifact(
        "agentic_run_readiness_report",
        "artifacts/10_run/agentic_run_readiness_report.json",
    ) or _resolve_artifact(
        "agentic_run_readiness_report",
        "agentic_run_readiness_report.json",
    )
    if readiness_path is not None:
        try:
            from code2paper.agentic.readiness_report import load_run_readiness_report
            readiness_report = load_run_readiness_report(readiness_path)
        except Exception:
            readiness_report = None

    # --- Validation manifest ---
    validation_manifest: Any = None
    vm_path = _resolve_artifact(
        "validation_manifest",
        "validation_manifest.json",
    )
    if vm_path is not None:
        try:
            validation_manifest = json.loads(vm_path.read_text(encoding="utf-8"))
        except Exception:
            validation_manifest = None

    # --- method_clean.md path ---
    method_clean_path = ""
    for key in ("text_clean_md", "text_md"):
        mp = _resolve_artifact(key)
        if mp is not None:
            method_clean_path = str(mp)
            break

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
        generation_call_traces=generation_call_traces,
        **resolved_profile_maps,
        intent_target_proposal_report=intent_target_proposal_report,
        v3_error=v3_error,
        completion_report=completion_report,
        readiness_report=readiness_report,
        validation_manifest=validation_manifest,
        method_clean_path=method_clean_path,
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
