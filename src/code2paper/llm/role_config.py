"""Per-role LLM generation config (Phase 1 R8 config basis).

This module is the single authority for role/node-specific LLM
sampling parameters used by the V3 research + writing pipeline.
The values mirror the Gemma-4 R8 protocol table in
``docs/agentic_r8_gemma4_progress_report_2026-07-20.md``:

===========  ============  =================  ===========  ========
Role          Temperature   Max output tokens  Top-p        Top-k
===========  ============  =================  ===========  ========
code_intake                0.20   2048                0.90        40
code_analyzer              0.20   4096                0.90        40
research_supervisor        0.20   1536                0.90        40
authoring_planner          0.40   2048                None        None
method_writer              0.70   8192 (default)      0.95        50
                                  12288 (extended)
                                  24576 (cumulative Method cap)
local_rewrite              0.35   3072                None        None
semantic_verifier          0.00   1024                None        None
deterministic_compiler     n/a    n/a                 n/a         n/a
===========  ============  =================  ===========  ========

Hard rules:

- Deterministic compiler/validator roles do NOT call the LLM.  Calling
  code must skip the LLM entirely for these roles.
- The 24576 cap is the cumulative budget for the *whole* Method
  document across all section calls; it is NOT a per-call default.
- Only ``finish_reason == "length"`` permits a writer to escalate from
  the default (8192) to the extended (12288) budget or to continue a
  truncated section.
- ``apply_role_config`` fills in role-specific defaults but NEVER
  overrides explicit per-call kwargs (caller-supplied values win).

Environment variable overrides (per-role):

- ``CODE2PAPER_LLM_TEMPERATURE_<ROLE>`` (e.g.,
  ``CODE2PAPER_LLM_TEMPERATURE_METHOD_WRITER``)
- ``CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_<ROLE>``
- ``CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_METHOD_WRITER_EXTENDED`` (the
  length-retry budget; defaults to 12288 and is separate from the writer's
  normal per-call default)
- ``CODE2PAPER_LLM_TOP_P_<ROLE>``
- ``CODE2PAPER_LLM_TOP_K_<ROLE>``

These overrides are read at call time so a single process can serve
multiple projects without restart.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final

from code2paper.schemas import LLMConfig, LLMProvider


# ---------------------------------------------------------------------------
# Role registry
# ---------------------------------------------------------------------------


RESEARCH_SUPERVISOR: Final[str] = "research_supervisor"
CODE_INTAKE: Final[str] = "code_intake"
CODE_ANALYZER: Final[str] = "code_analyzer"
INTENT_COMPILER: Final[str] = "intent_compiler"
AUTHORING_PLANNER: Final[str] = "authoring_planner"
METHOD_WRITER: Final[str] = "method_writer"
LOCAL_REWRITE: Final[str] = "local_rewrite"
SEMANTIC_VERIFIER: Final[str] = "semantic_verifier"
# Deterministic roles — never invoke the LLM.
DETERMINISTIC_COMPILER: Final[str] = "deterministic_compiler"
DETERMINISTIC_VALIDATOR: Final[str] = "deterministic_validator"


#: Tuple of all roles that DO call the LLM.  Used by R8 acceptance to
#: verify per-role sampling config evidence is present.
LLM_CALLING_ROLES: Final[tuple[str, ...]] = (
    INTENT_COMPILER,
    CODE_INTAKE,
    CODE_ANALYZER,
    RESEARCH_SUPERVISOR,
    AUTHORING_PLANNER,
    METHOD_WRITER,
    LOCAL_REWRITE,
    SEMANTIC_VERIFIER,
)

#: Roles that must NOT call the LLM.  Encountering an LLM call log
#: tagged with one of these roles is a protocol violation.
DETERMINISTIC_ROLES: Final[tuple[str, ...]] = (
    DETERMINISTIC_COMPILER,
    DETERMINISTIC_VALIDATOR,
)


# ---------------------------------------------------------------------------
# Role generation config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoleGenerationConfig:
    """Per-role default sampling config.

    ``max_output_tokens_default`` is the per-call default; the
    method_writer role additionally exposes ``max_output_tokens_extended``
    (used only when ``finish_reason == "length"``) and
    ``cumulative_budget`` (the whole-Method cap).
    """

    role: str
    temperature: float
    max_output_tokens_default: int
    max_output_tokens_extended: int | None = None
    cumulative_budget: int | None = None
    top_p: float | None = None
    top_k: int | None = None
    # When True, callers MUST NOT issue LLM requests for this role.
    deterministic: bool = False

    def max_output_tokens(self, *, extended: bool = False) -> int:
        """Return the per-call max output token budget.

        When ``extended`` is True (only valid for the method_writer
        role), returns the extended budget; otherwise returns the
        default.
        """

        if extended and self.max_output_tokens_extended is not None:
            return self.max_output_tokens_extended
        return self.max_output_tokens_default


#: Frozen registry of role-specific defaults.  These are the audited
#: values from the R8 protocol table; environment overrides are
#: applied on top by :func:`apply_role_config`.
ROLE_GENERATION_CONFIGS: Final[dict[str, RoleGenerationConfig]] = {
    CODE_INTAKE: RoleGenerationConfig(
        role=CODE_INTAKE,
        temperature=0.20,
        max_output_tokens_default=2048,
        top_p=0.90,
        top_k=40,
    ),
    CODE_ANALYZER: RoleGenerationConfig(
        role=CODE_ANALYZER,
        temperature=0.20,
        max_output_tokens_default=4096,
        top_p=0.90,
        top_k=40,
    ),
    INTENT_COMPILER: RoleGenerationConfig(
        role=INTENT_COMPILER,
        temperature=0.20,
        max_output_tokens_default=4096,
    ),
    RESEARCH_SUPERVISOR: RoleGenerationConfig(
        role=RESEARCH_SUPERVISOR,
        temperature=0.20,
        max_output_tokens_default=1536,
        top_p=0.90,
        top_k=40,
    ),
    AUTHORING_PLANNER: RoleGenerationConfig(
        role=AUTHORING_PLANNER,
        temperature=0.40,
        max_output_tokens_default=2048,
    ),
    METHOD_WRITER: RoleGenerationConfig(
        role=METHOD_WRITER,
        temperature=0.70,
        max_output_tokens_default=8192,
        max_output_tokens_extended=12288,
        cumulative_budget=24576,
        top_p=0.95,
        top_k=50,
    ),
    LOCAL_REWRITE: RoleGenerationConfig(
        role=LOCAL_REWRITE,
        temperature=0.35,
        max_output_tokens_default=3072,
    ),
    SEMANTIC_VERIFIER: RoleGenerationConfig(
        role=SEMANTIC_VERIFIER,
        temperature=0.00,
        max_output_tokens_default=1024,
    ),
    DETERMINISTIC_COMPILER: RoleGenerationConfig(
        role=DETERMINISTIC_COMPILER,
        temperature=0.0,
        max_output_tokens_default=0,
        deterministic=True,
    ),
    DETERMINISTIC_VALIDATOR: RoleGenerationConfig(
        role=DETERMINISTIC_VALIDATOR,
        temperature=0.0,
        max_output_tokens_default=0,
        deterministic=True,
    ),
}


def role_generation_config(role: str) -> RoleGenerationConfig:
    """Return the frozen :class:`RoleGenerationConfig` for ``role``.

    Raises ``KeyError`` when ``role`` is not in
    :data:`ROLE_GENERATION_CONFIGS`.  Calling code should only pass
    validated role names (use :func:`is_llm_calling_role` /
    :func:`is_deterministic_role` to check first).
    """

    return ROLE_GENERATION_CONFIGS[role]


def is_llm_calling_role(role: str) -> bool:
    """Return True when ``role`` is one of the LLM-calling roles."""

    return role in LLM_CALLING_ROLES


def is_deterministic_role(role: str) -> bool:
    """Return True when ``role`` must NOT call the LLM."""

    return role in DETERMINISTIC_ROLES


def known_role(role: str) -> bool:
    """Return True when ``role`` is in the registry."""

    return role in ROLE_GENERATION_CONFIGS


# ---------------------------------------------------------------------------
# Role-config application
# ---------------------------------------------------------------------------


def apply_role_config(
    base_config: LLMConfig,
    role: str,
    *,
    extended_writer_budget: bool = False,
) -> LLMConfig:
    """Return a new :class:`LLMConfig` with role-specific defaults applied.

    The ``role`` field is always set on the returned config so
    downstream tracing / R8 checks can attribute the call to the
    correct role.

    Override precedence (highest first):

    1. Explicit fields on ``base_config`` (caller-supplied values).
       A field is considered "explicit" when it differs from the
       ``LLMConfig`` default.  Concretely: ``temperature`` is explicit
       when the caller passed a non-default value; ``top_p`` / ``top_k``
       / ``seed`` are explicit when not ``None``; ``max_output_tokens``
       is explicit when it is not the ``LLMConfig`` default (12000).
    2. Per-role environment variable overrides
       (``CODE2PAPER_LLM_TEMPERATURE_<ROLE>`` etc.).
    3. Frozen role defaults from :data:`ROLE_GENERATION_CONFIGS`.

    For the ``method_writer`` role, ``extended_writer_budget=True``
    selects the extended (12288) budget; the default is 8192.

    For deterministic roles, the returned config has ``provider=NONE``
    so any LLM call attempt becomes a no-op (defensive — callers
    should still skip LLM calls for deterministic roles).
    """

    if role not in ROLE_GENERATION_CONFIGS:
        raise KeyError(f"unknown role: {role!r}")

    role_cfg = ROLE_GENERATION_CONFIGS[role]

    if role_cfg.deterministic:
        # Force provider=NONE so any accidental LLM call is a no-op.
        return base_config.model_copy(
            update={
                "role": role,
                "provider": LLMProvider.NONE,
                "temperature": 0.0,
                "max_output_tokens": 0,
                "top_p": None,
                "top_k": None,
                "seed": None,
            }
        )

    env_temp = _role_env_float(role, "TEMPERATURE")
    env_max_tokens = _role_env_int(role, "MAX_OUTPUT_TOKENS")
    env_top_p = _role_env_float(role, "TOP_P")
    env_top_k = _role_env_int(role, "TOP_K")

    # Resolve temperature: explicit base_config value wins, then env,
    # then role default.  We detect "explicit base_config" by checking
    # whether the value differs from BOTH sentinel values:
    #
    # - 0.2 is the ``LLMConfig`` default (caller did not set it).
    # - 0.0 is the R8 acceptance baseline (``CODE2PAPER_LLM_TEMPERATURE=0``
    #   sets this globally, but per-role defaults should still apply so
    #   the per-role sampling protocol is honored during formal R8
    #   verification).
    #
    # Treating both as sentinels lets the R8 protocol's global
    # ``CODE2PAPER_LLM_TEMPERATURE=0`` coexist with per-role
    # temperatures (0.20 / 0.40 / 0.70 / 0.35 / 0.00).  Callers that
    # genuinely need to override a role's temperature to 0.0 should
    # use the per-role env var
    # ``CODE2PAPER_LLM_TEMPERATURE_<ROLE>=0.0``.
    base_temp_explicit = (
        abs(base_config.temperature - 0.0) > 1e-9
        and abs(base_config.temperature - 0.2) > 1e-9
    )
    if base_temp_explicit:
        final_temperature = base_config.temperature
    elif env_temp is not None:
        final_temperature = env_temp
    else:
        final_temperature = role_cfg.temperature

    # Resolve max_output_tokens.  A writer length retry deliberately does
    # NOT reuse ``CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_METHOD_WRITER``: that
    # variable is the normal 8192-token budget.  It instead uses the
    # separately overridable extended ceiling, preserving the audited
    # 8192 -> 12288 escalation in the formal environment profile.
    base_tokens_explicit = base_config.max_output_tokens != 12000
    writer_extended_env = (
        _read_int("CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_METHOD_WRITER_EXTENDED")
        if role == METHOD_WRITER and extended_writer_budget
        else None
    )
    if base_tokens_explicit:
        final_max_tokens = base_config.max_output_tokens
    elif writer_extended_env is not None:
        final_max_tokens = writer_extended_env
    elif role == METHOD_WRITER and extended_writer_budget:
        final_max_tokens = role_cfg.max_output_tokens(extended=True)
    elif env_max_tokens is not None:
        final_max_tokens = env_max_tokens
    else:
        final_max_tokens = role_cfg.max_output_tokens(extended=extended_writer_budget)

    # Resolve top_p / top_k / seed: explicit base_config value wins,
    # then env, then role default (which is None for all roles in the
    # current registry).
    final_top_p = base_config.top_p
    if final_top_p is None:
        final_top_p = env_top_p if env_top_p is not None else role_cfg.top_p
    final_top_k = base_config.top_k
    if final_top_k is None:
        final_top_k = env_top_k if env_top_k is not None else role_cfg.top_k
    final_seed = base_config.seed  # No env override for seed (yet).

    return base_config.model_copy(
        update={
            "role": role,
            "temperature": final_temperature,
            "max_output_tokens": final_max_tokens,
            "top_p": final_top_p,
            "top_k": final_top_k,
            "seed": final_seed,
        }
    )


def writer_cumulative_budget() -> int:
    """Return the cumulative Method output token budget.

    This is the 24576-token cap across all section calls for a single
    Method document.  Writer code must track cumulative usage and stop
    issuing further LLM calls once the budget is exhausted.
    """

    return ROLE_GENERATION_CONFIGS[METHOD_WRITER].cumulative_budget or 24576


def writer_default_budget() -> int:
    """Return the per-call default output token budget for the writer."""

    return ROLE_GENERATION_CONFIGS[METHOD_WRITER].max_output_tokens_default


def writer_extended_budget() -> int:
    """Return the per-call extended output token budget for the writer.

    Only used when ``finish_reason == "length"`` indicates the default
    budget was insufficient.
    """

    extended = ROLE_GENERATION_CONFIGS[METHOD_WRITER].max_output_tokens_extended
    return extended or writer_default_budget()


# ---------------------------------------------------------------------------
# Role-specific env var helpers
# ---------------------------------------------------------------------------


def _role_env_float(role: str, suffix: str) -> float | None:
    name = _role_env_name(role, suffix)
    return _read_float(name)


def _role_env_int(role: str, suffix: str) -> int | None:
    name = _role_env_name(role, suffix)
    return _read_int(name)


def _role_env_name(role: str, suffix: str) -> str:
    return f"CODE2PAPER_LLM_{suffix.upper()}_{role.upper()}"


def _read_float(name: str) -> float | None:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _read_int(name: str) -> int | None:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


__all__ = [
    "AUTHORING_PLANNER",
    "CODE_ANALYZER",
    "CODE_INTAKE",
    "DETERMINISTIC_COMPILER",
    "DETERMINISTIC_ROLES",
    "DETERMINISTIC_VALIDATOR",
    "INTENT_COMPILER",
    "LLM_CALLING_ROLES",
    "LOCAL_REWRITE",
    "METHOD_WRITER",
    "RESEARCH_SUPERVISOR",
    "ROLE_GENERATION_CONFIGS",
    "SEMANTIC_VERIFIER",
    "RoleGenerationConfig",
    "apply_role_config",
    "is_deterministic_role",
    "is_llm_calling_role",
    "known_role",
    "role_generation_config",
    "writer_cumulative_budget",
    "writer_default_budget",
    "writer_extended_budget",
]
