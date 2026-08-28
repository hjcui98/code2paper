"""Tests for ``code2paper.llm.role_config`` (Phase 1 R8 config basis).

Verifies the per-role generation config table, the ``apply_role_config``
override precedence (explicit > env > role default), the writer
cumulative budget helpers, and the deterministic-role guard.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from code2paper.llm.role_config import (
    AUTHORING_PLANNER,
    CODE_ANALYZER,
    CODE_INTAKE,
    DETERMINISTIC_COMPILER,
    DETERMINISTIC_ROLES,
    DETERMINISTIC_VALIDATOR,
    INTENT_COMPILER,
    LLM_CALLING_ROLES,
    LOCAL_REWRITE,
    METHOD_MECHANISM_DRAFT_PLANNER,
    METHOD_SECTION_FORMALIZER,
    METHOD_WRITER,
    RESEARCH_SUPERVISOR,
    ROLE_GENERATION_CONFIGS,
    SEMANTIC_VERIFIER,
    RoleGenerationConfig,
    apply_role_config,
    is_deterministic_role,
    is_llm_calling_role,
    known_role,
    role_generation_config,
    writer_cumulative_budget,
    writer_default_budget,
    writer_extended_budget,
)
from code2paper.schemas import LLMConfig, LLMProvider


def _base_config(**overrides) -> LLMConfig:
    """Build the canonical base LLMConfig used in tests."""

    defaults = dict(
        provider=LLMProvider.OPENAI,
        model="gemma4-31b-nvfp4",
        temperature=0.2,
        max_output_tokens=12000,
        cache=False,
    )
    defaults.update(overrides)
    return LLMConfig(**defaults)


class RoleRegistryTests(unittest.TestCase):
    """Tests for the role registry constants."""

    def test_llm_calling_roles_has_eleven_roles(self) -> None:
        self.assertEqual(len(LLM_CALLING_ROLES), 11)
        self.assertIn(INTENT_COMPILER, LLM_CALLING_ROLES)
        self.assertIn(CODE_INTAKE, LLM_CALLING_ROLES)
        self.assertIn(CODE_ANALYZER, LLM_CALLING_ROLES)
        self.assertIn(RESEARCH_SUPERVISOR, LLM_CALLING_ROLES)
        self.assertIn(AUTHORING_PLANNER, LLM_CALLING_ROLES)
        self.assertIn(METHOD_MECHANISM_DRAFT_PLANNER, LLM_CALLING_ROLES)
        self.assertIn(METHOD_SECTION_FORMALIZER, LLM_CALLING_ROLES)
        self.assertIn(METHOD_WRITER, LLM_CALLING_ROLES)
        self.assertIn(LOCAL_REWRITE, LLM_CALLING_ROLES)
        self.assertIn(SEMANTIC_VERIFIER, LLM_CALLING_ROLES)

    def test_deterministic_roles_has_two_roles(self) -> None:
        self.assertEqual(len(DETERMINISTIC_ROLES), 2)
        self.assertIn(DETERMINISTIC_COMPILER, DETERMINISTIC_ROLES)
        self.assertIn(DETERMINISTIC_VALIDATOR, DETERMINISTIC_ROLES)

    def test_llm_calling_and_deterministic_roles_are_disjoint(self) -> None:
        self.assertEqual(set(LLM_CALLING_ROLES) & set(DETERMINISTIC_ROLES), set())

    def test_is_llm_calling_role(self) -> None:
        for role in LLM_CALLING_ROLES:
            self.assertTrue(is_llm_calling_role(role), f"{role} should be LLM-calling")
        for role in DETERMINISTIC_ROLES:
            self.assertFalse(is_llm_calling_role(role), f"{role} should not be LLM-calling")
        self.assertFalse(is_llm_calling_role("unknown_role"))

    def test_is_deterministic_role(self) -> None:
        for role in DETERMINISTIC_ROLES:
            self.assertTrue(is_deterministic_role(role), f"{role} should be deterministic")
        for role in LLM_CALLING_ROLES:
            self.assertFalse(is_deterministic_role(role), f"{role} should not be deterministic")
        self.assertFalse(is_deterministic_role("unknown_role"))

    def test_known_role(self) -> None:
        for role in LLM_CALLING_ROLES + DETERMINISTIC_ROLES:
            self.assertTrue(known_role(role), f"{role} should be known")
        self.assertFalse(known_role("unknown_role"))

    def test_role_generation_config_returns_frozen_registry_entry(self) -> None:
        cfg = role_generation_config(RESEARCH_SUPERVISOR)
        self.assertIs(cfg, ROLE_GENERATION_CONFIGS[RESEARCH_SUPERVISOR])

    def test_role_generation_config_raises_for_unknown_role(self) -> None:
        with self.assertRaises(KeyError):
            role_generation_config("unknown_role")


class RoleGenerationConfigTableTests(unittest.TestCase):
    """Tests for the frozen role config table values.

    The values here are the audited R8 protocol values from
    ``docs/agentic_r8_gemma4_progress_report_2026-07-20.md``.  Any
    change to these values must be reflected in the protocol doc and
    the R8 acceptance checker's per-role verification.
    """

    def test_intent_compiler_protocol(self) -> None:
        config = ROLE_GENERATION_CONFIGS[INTENT_COMPILER]
        self.assertEqual(config.temperature, 0.20)
        self.assertEqual(config.max_output_tokens_default, 4096)

    def test_research_supervisor_temperature_is_0_20(self) -> None:
        self.assertEqual(ROLE_GENERATION_CONFIGS[RESEARCH_SUPERVISOR].temperature, 0.20)

    def test_authoring_planner_temperature_is_0_40(self) -> None:
        self.assertEqual(ROLE_GENERATION_CONFIGS[AUTHORING_PLANNER].temperature, 0.40)

    def test_method_writer_temperature_is_0_70(self) -> None:
        self.assertEqual(ROLE_GENERATION_CONFIGS[METHOD_WRITER].temperature, 0.70)

    def test_mechanism_draft_planner_budget_is_8192(self) -> None:
        self.assertEqual(
            ROLE_GENERATION_CONFIGS[METHOD_MECHANISM_DRAFT_PLANNER].max_output_tokens_default,
            8192,
        )

    def test_section_formalizer_uses_low_temperature_and_8192_budget(self) -> None:
        config = ROLE_GENERATION_CONFIGS[METHOD_SECTION_FORMALIZER]
        self.assertLessEqual(config.temperature, 0.2)
        self.assertEqual(config.max_output_tokens_default, 8192)

    def test_local_rewrite_temperature_is_0_35(self) -> None:
        self.assertEqual(ROLE_GENERATION_CONFIGS[LOCAL_REWRITE].temperature, 0.35)

    def test_semantic_verifier_temperature_is_0_00(self) -> None:
        self.assertEqual(ROLE_GENERATION_CONFIGS[SEMANTIC_VERIFIER].temperature, 0.00)

    def test_research_supervisor_default_budget_is_4096(self) -> None:
        # A 3-tool-call proposal with goal/rationale/evidence payloads
        # exceeded 1536 tokens on the fresh EBCAR run (truncated JSON,
        # llm_parse_error); the budget was raised again after the 3072
        # envelope still sat far below the local 131072 context window.
        self.assertEqual(ROLE_GENERATION_CONFIGS[RESEARCH_SUPERVISOR].max_output_tokens_default, 4096)

    def test_embedded_intake_and_analyzer_budgets_have_distinct_roles(self) -> None:
        self.assertEqual(ROLE_GENERATION_CONFIGS[CODE_INTAKE].max_output_tokens_default, 4096)
        self.assertEqual(ROLE_GENERATION_CONFIGS[CODE_ANALYZER].max_output_tokens_default, 4096)

    def test_research_supervisor_sampling_defaults_are_gemma_tuned(self) -> None:
        config = ROLE_GENERATION_CONFIGS[RESEARCH_SUPERVISOR]
        self.assertEqual(config.top_p, 0.90)
        self.assertEqual(config.top_k, 40)

    def test_authoring_planner_default_budget_is_4096(self) -> None:
        self.assertEqual(ROLE_GENERATION_CONFIGS[AUTHORING_PLANNER].max_output_tokens_default, 4096)

    def test_method_writer_default_budget_is_8192(self) -> None:
        self.assertEqual(ROLE_GENERATION_CONFIGS[METHOD_WRITER].max_output_tokens_default, 8192)

    def test_method_writer_extended_budget_is_12288(self) -> None:
        self.assertEqual(ROLE_GENERATION_CONFIGS[METHOD_WRITER].max_output_tokens_extended, 12288)

    def test_method_writer_cumulative_budget_is_24576(self) -> None:
        self.assertEqual(ROLE_GENERATION_CONFIGS[METHOD_WRITER].cumulative_budget, 24576)

    def test_method_writer_sampling_defaults_are_prose_creative(self) -> None:
        config = ROLE_GENERATION_CONFIGS[METHOD_WRITER]
        self.assertEqual(config.temperature, 0.70)
        self.assertEqual(config.top_p, 0.90)
        self.assertEqual(config.top_k, 50)
        self.assertEqual(config.seed, 42)

    def test_local_rewrite_default_budget_is_3072(self) -> None:
        self.assertEqual(ROLE_GENERATION_CONFIGS[LOCAL_REWRITE].max_output_tokens_default, 3072)

    def test_semantic_verifier_default_budget_is_2048(self) -> None:
        self.assertEqual(ROLE_GENERATION_CONFIGS[SEMANTIC_VERIFIER].max_output_tokens_default, 2048)

    def test_deterministic_compiler_is_marked_deterministic(self) -> None:
        self.assertTrue(ROLE_GENERATION_CONFIGS[DETERMINISTIC_COMPILER].deterministic)

    def test_deterministic_validator_is_marked_deterministic(self) -> None:
        self.assertTrue(ROLE_GENERATION_CONFIGS[DETERMINISTIC_VALIDATOR].deterministic)

    def test_llm_calling_roles_are_not_deterministic(self) -> None:
        for role in LLM_CALLING_ROLES:
            self.assertFalse(ROLE_GENERATION_CONFIGS[role].deterministic, f"{role} must not be deterministic")

    def test_role_generation_config_max_output_tokens_extended_returns_default_when_false(self) -> None:
        cfg = ROLE_GENERATION_CONFIGS[METHOD_WRITER]
        self.assertEqual(cfg.max_output_tokens(extended=False), 8192)

    def test_role_generation_config_max_output_tokens_extended_returns_extended_when_true(self) -> None:
        cfg = ROLE_GENERATION_CONFIGS[METHOD_WRITER]
        self.assertEqual(cfg.max_output_tokens(extended=True), 12288)

    def test_role_generation_config_max_output_tokens_extended_falls_back_when_none(self) -> None:
        # Roles without an extended budget fall back to the default
        # even when extended=True is requested.
        cfg = ROLE_GENERATION_CONFIGS[RESEARCH_SUPERVISOR]
        self.assertIsNone(cfg.max_output_tokens_extended)
        self.assertEqual(cfg.max_output_tokens(extended=True), 4096)


class WriterBudgetHelpersTests(unittest.TestCase):
    """Tests for the writer_cumulative_budget / default / extended helpers."""

    def test_writer_cumulative_budget_is_24576(self) -> None:
        self.assertEqual(writer_cumulative_budget(), 24576)

    def test_writer_default_budget_is_8192(self) -> None:
        self.assertEqual(writer_default_budget(), 8192)

    def test_writer_extended_budget_is_12288(self) -> None:
        self.assertEqual(writer_extended_budget(), 12288)


class ApplyRoleConfigTests(unittest.TestCase):
    """Tests for ``apply_role_config`` override precedence."""

    def test_apply_role_config_sets_role_field(self) -> None:
        cfg = apply_role_config(_base_config(), RESEARCH_SUPERVISOR)
        self.assertEqual(cfg.role, RESEARCH_SUPERVISOR)

    def test_apply_role_config_uses_role_default_temperature(self) -> None:
        cfg = apply_role_config(_base_config(), RESEARCH_SUPERVISOR)
        self.assertEqual(cfg.temperature, 0.20)

    def test_apply_role_config_uses_role_default_max_output_tokens(self) -> None:
        env = {
            "CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_AUTHORING_PLANNER": "",
            "CODE2PAPER_LLM_MAX_OUTPUT_TOKENS": "",
        }
        with patch.dict("os.environ", env, clear=False):
            cfg = apply_role_config(_base_config(), AUTHORING_PLANNER)
            self.assertEqual(cfg.max_output_tokens, 4096)

    def test_apply_role_config_writer_default_budget_is_8192(self) -> None:
        cfg = apply_role_config(_base_config(), METHOD_WRITER)
        self.assertEqual(cfg.max_output_tokens, 8192)

    def test_apply_role_config_writer_extended_budget_is_12288(self) -> None:
        cfg = apply_role_config(_base_config(), METHOD_WRITER, extended_writer_budget=True)
        self.assertEqual(cfg.max_output_tokens, 12288)

    def test_writer_env_default_does_not_disable_length_retry_budget(self) -> None:
        """Formal 8192 default still escalates to 12288 on a length retry."""

        env = {"CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_METHOD_WRITER": "8192"}
        with patch.dict("os.environ", env, clear=False):
            normal = apply_role_config(_base_config(), METHOD_WRITER)
            extended = apply_role_config(
                _base_config(), METHOD_WRITER, extended_writer_budget=True
            )
        self.assertEqual(normal.max_output_tokens, 8192)
        self.assertEqual(extended.max_output_tokens, 12288)

    def test_writer_extended_env_override_applies_only_to_length_retry(self) -> None:
        env = {
            "CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_METHOD_WRITER": "8192",
            "CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_METHOD_WRITER_EXTENDED": "11000",
        }
        with patch.dict("os.environ", env, clear=False):
            normal = apply_role_config(_base_config(), METHOD_WRITER)
            extended = apply_role_config(
                _base_config(), METHOD_WRITER, extended_writer_budget=True
            )
        self.assertEqual(normal.max_output_tokens, 8192)
        self.assertEqual(extended.max_output_tokens, 11000)

    def test_apply_role_config_explicit_base_temperature_wins(self) -> None:
        cfg = apply_role_config(_base_config(temperature=0.05), RESEARCH_SUPERVISOR)
        self.assertEqual(cfg.temperature, 0.05)

    def test_apply_role_config_explicit_base_max_output_tokens_wins(self) -> None:
        cfg = apply_role_config(_base_config(max_output_tokens=4096), RESEARCH_SUPERVISOR)
        self.assertEqual(cfg.max_output_tokens, 4096)

    def test_apply_role_config_explicit_base_top_p_wins(self) -> None:
        cfg = apply_role_config(_base_config(top_p=0.5), RESEARCH_SUPERVISOR)
        self.assertEqual(cfg.top_p, 0.5)

    def test_apply_role_config_explicit_base_top_k_wins(self) -> None:
        cfg = apply_role_config(_base_config(top_k=10), RESEARCH_SUPERVISOR)
        self.assertEqual(cfg.top_k, 10)

    def test_apply_role_config_explicit_base_seed_wins(self) -> None:
        cfg = apply_role_config(_base_config(seed=42), RESEARCH_SUPERVISOR)
        self.assertEqual(cfg.seed, 42)

    def test_apply_role_config_env_temperature_override_wins_over_role_default(self) -> None:
        env = {"CODE2PAPER_LLM_TEMPERATURE_RESEARCH_SUPERVISOR": "0.10"}
        with patch.dict("os.environ", env, clear=False):
            cfg = apply_role_config(_base_config(), RESEARCH_SUPERVISOR)
        self.assertEqual(cfg.temperature, 0.10)

    def test_apply_role_config_env_max_output_tokens_override_wins_over_role_default(self) -> None:
        env = {"CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_METHOD_WRITER": "10000"}
        with patch.dict("os.environ", env, clear=False):
            cfg = apply_role_config(_base_config(), METHOD_WRITER)
        self.assertEqual(cfg.max_output_tokens, 10000)

    def test_apply_role_config_global_env_temperature_is_baseline_role_default_wins(self) -> None:
        env = {"CODE2PAPER_LLM_TEMPERATURE": "0.6"}
        with patch.dict("os.environ", env, clear=False):
            cfg = apply_role_config(_base_config(temperature=0.6), METHOD_WRITER)
        self.assertEqual(cfg.temperature, 0.70)

    def test_apply_role_config_per_role_env_still_wins_over_global_baseline(self) -> None:
        env = {
            "CODE2PAPER_LLM_TEMPERATURE": "0.6",
            "CODE2PAPER_LLM_TEMPERATURE_METHOD_WRITER": "0.05",
        }
        with patch.dict("os.environ", env, clear=False):
            cfg = apply_role_config(_base_config(temperature=0.6), METHOD_WRITER)
        self.assertEqual(cfg.temperature, 0.05)

    def test_apply_role_config_explicit_base_temperature_beats_env_override(self) -> None:
        env = {"CODE2PAPER_LLM_TEMPERATURE_RESEARCH_SUPERVISOR": "0.10"}
        with patch.dict("os.environ", env, clear=False):
            cfg = apply_role_config(_base_config(temperature=0.07), RESEARCH_SUPERVISOR)
        self.assertEqual(cfg.temperature, 0.07)

    def test_apply_role_config_env_top_p_override(self) -> None:
        env = {"CODE2PAPER_LLM_TOP_P_METHOD_WRITER": "0.9"}
        with patch.dict("os.environ", env, clear=False):
            cfg = apply_role_config(_base_config(), METHOD_WRITER)
        self.assertEqual(cfg.top_p, 0.9)

    def test_apply_role_config_env_top_k_override(self) -> None:
        env = {"CODE2PAPER_LLM_TOP_K_METHOD_WRITER": "20"}
        with patch.dict("os.environ", env, clear=False):
            cfg = apply_role_config(_base_config(), METHOD_WRITER)
        self.assertEqual(cfg.top_k, 20)

    def test_reasoning_none_clears_incompatible_thinking_budget(self) -> None:
        env = {
            "CODE2PAPER_LLM_REASONING_EFFORT_METHOD_WRITER": "none",
            "CODE2PAPER_LLM_THINKING_TOKEN_BUDGET_METHOD_WRITER": "1024",
        }
        with patch.dict("os.environ", env, clear=False):
            cfg = apply_role_config(_base_config(), METHOD_WRITER)
        self.assertEqual(cfg.reasoning_effort, "none")
        self.assertIsNone(cfg.thinking_token_budget)

    def test_apply_role_config_deterministic_role_forces_provider_none(self) -> None:
        cfg = apply_role_config(_base_config(), DETERMINISTIC_COMPILER)
        self.assertEqual(cfg.provider, LLMProvider.NONE)

    def test_apply_role_config_deterministic_role_zeroes_temperature(self) -> None:
        cfg = apply_role_config(_base_config(temperature=0.5), DETERMINISTIC_COMPILER)
        self.assertEqual(cfg.temperature, 0.0)

    def test_apply_role_config_deterministic_role_zeroes_max_output_tokens(self) -> None:
        cfg = apply_role_config(_base_config(max_output_tokens=4096), DETERMINISTIC_COMPILER)
        self.assertEqual(cfg.max_output_tokens, 0)

    def test_apply_role_config_deterministic_role_clears_top_p_top_k_seed(self) -> None:
        cfg = apply_role_config(
            _base_config(top_p=0.5, top_k=10, seed=42),
            DETERMINISTIC_COMPILER,
        )
        self.assertIsNone(cfg.top_p)
        self.assertIsNone(cfg.top_k)
        self.assertIsNone(cfg.seed)

    def test_apply_role_config_raises_for_unknown_role(self) -> None:
        with self.assertRaises(KeyError):
            apply_role_config(_base_config(), "unknown_role")

    def test_apply_role_config_preserves_provider_for_llm_calling_role(self) -> None:
        cfg = apply_role_config(_base_config(), METHOD_WRITER)
        self.assertEqual(cfg.provider, LLMProvider.OPENAI)

    def test_apply_role_config_preserves_model(self) -> None:
        cfg = apply_role_config(_base_config(), METHOD_WRITER)
        self.assertEqual(cfg.model, "gemma4-31b-nvfp4")

    def test_apply_role_config_preserves_cache_flag(self) -> None:
        cfg = apply_role_config(_base_config(cache=False), METHOD_WRITER)
        self.assertFalse(cfg.cache)

    def test_apply_role_config_preserves_max_input_tokens(self) -> None:
        cfg = apply_role_config(_base_config(max_input_tokens=90000), METHOD_WRITER)
        self.assertEqual(cfg.max_input_tokens, 90000)

    def test_apply_role_config_env_top_p_empty_string_is_ignored(self) -> None:
        # Empty env var should be treated as unset (not 0.0).
        env = {"CODE2PAPER_LLM_TOP_P_METHOD_WRITER": ""}
        with patch.dict("os.environ", env, clear=False):
            cfg = apply_role_config(_base_config(), METHOD_WRITER)
        self.assertEqual(cfg.top_p, 0.90)

    def test_apply_role_config_env_top_p_invalid_string_is_ignored(self) -> None:
        env = {"CODE2PAPER_LLM_TOP_P_METHOD_WRITER": "not-a-number"}
        with patch.dict("os.environ", env, clear=False):
            cfg = apply_role_config(_base_config(), METHOD_WRITER)
        self.assertEqual(cfg.top_p, 0.90)

    # ------------------------------------------------------------------
    # R8 acceptance coexistence: ``CODE2PAPER_LLM_TEMPERATURE=0`` must
    # not override per-role protocol temperatures.  ``0.0`` and ``0.2``
    # (LLMConfig default) are both treated as sentinel values so the
    # per-role default (0.20 / 0.40 / 0.70 / 0.35 / 0.00) wins.
    # ------------------------------------------------------------------

    def test_apply_role_config_base_temperature_zero_does_not_override_role_default(self) -> None:
        """R8 protocol: CODE2PAPER_LLM_TEMPERATURE=0 must not clobber per-role temps."""
        for role in LLM_CALLING_ROLES:
            cfg = apply_role_config(_base_config(temperature=0.0), role)
            expected = ROLE_GENERATION_CONFIGS[role].temperature
            self.assertEqual(
                cfg.temperature,
                expected,
                f"{role}: base temp=0.0 should defer to role default {expected}",
            )

    def test_apply_role_config_base_temperature_zero_uses_env_when_present(self) -> None:
        """Per-role env override still wins when base temp is the 0.0 sentinel."""
        env = {"CODE2PAPER_LLM_TEMPERATURE_RESEARCH_SUPERVISOR": "0.15"}
        with patch.dict("os.environ", env, clear=False):
            cfg = apply_role_config(_base_config(temperature=0.0), RESEARCH_SUPERVISOR)
        self.assertEqual(cfg.temperature, 0.15)

    def test_apply_role_config_explicit_zero_via_env_is_respected(self) -> None:
        """Callers can still force temperature=0.0 via the per-role env var."""
        env = {"CODE2PAPER_LLM_TEMPERATURE_METHOD_WRITER": "0.0"}
        with patch.dict("os.environ", env, clear=False):
            cfg = apply_role_config(_base_config(temperature=0.2), METHOD_WRITER)
        self.assertEqual(cfg.temperature, 0.0)

    def test_apply_role_config_explicit_non_sentinel_temperature_still_wins(self) -> None:
        """Sanity: non-sentinel explicit temperatures (e.g., 0.05) still win."""
        cfg = apply_role_config(_base_config(temperature=0.05), RESEARCH_SUPERVISOR)
        self.assertEqual(cfg.temperature, 0.05)


class RoleGenerationConfigDataclassTests(unittest.TestCase):
    """Tests for the RoleGenerationConfig dataclass itself."""

    def test_role_generation_config_is_frozen(self) -> None:
        cfg = RoleGenerationConfig(role="x", temperature=0.0, max_output_tokens_default=1)
        with self.assertRaises(Exception):
            cfg.temperature = 1.0  # type: ignore[misc]

    def test_role_output_budget_audit_covers_every_registered_role(self) -> None:
        from code2paper.llm.role_config import (
            LLM_CALLING_ROLES,
            ROLE_GENERATION_CONFIGS,
            role_output_budget_audit,
        )

        rows = role_output_budget_audit()
        self.assertEqual(
            {row["role"] for row in rows},
            set(ROLE_GENERATION_CONFIGS),
        )
        for row in rows:
            self.assertIn(row["finish_reason_observation"], {"length", "structured_complete"})
            if row["role"] in LLM_CALLING_ROLES and row["max_output_tokens_default"] > 0:
                self.assertGreaterEqual(row["max_output_tokens_default"], 2048)


if __name__ == "__main__":
    unittest.main()
