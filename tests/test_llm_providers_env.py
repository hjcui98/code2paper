"""Tests for ``code2paper.llm.providers`` env var resolution (Phase 1).

Verifies the LLM configuration environment-variable contract mandated
by the V3 R8 protocol:

- ``CODE2PAPER_OPENAI_BASE_URL=http://127.0.0.1:8000/v1`` resolves to
  the local Gemma vLLM endpoint at
  ``http://127.0.0.1:8000/v1/chat/completions``.
- The loopback URL is recognized as a local deployment so
  ``has_provider_api_key`` returns True without an API key.
- The new per-role sampling env vars (``CODE2PAPER_LLM_TOP_P``,
  ``CODE2PAPER_LLM_TOP_K``, ``CODE2PAPER_LLM_SEED``,
  ``CODE2PAPER_LLM_MAX_INPUT_TOKENS``, ``CODE2PAPER_LLM_ROLE``) are
  loaded into :class:`LLMConfig`.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from code2paper.llm.capabilities import is_loopback_url
from code2paper.llm.providers import (
    has_provider_api_key,
    load_llm_config_from_env,
    openai_compatible_base_url,
)
from code2paper.schemas import LLMConfig, LLMProvider


class Code2PaperOpenaiBaseUrlTests(unittest.TestCase):
    """Verifies the canonical Gemma vLLM endpoint env var."""

    def test_code2paper_openai_base_url_resolves_to_loopback_v1(self) -> None:
        """``CODE2PAPER_OPENAI_BASE_URL=http://127.0.0.1:8000/v1`` resolves
        to ``http://127.0.0.1:8000/v1/chat/completions``."""

        env = {"CODE2PAPER_OPENAI_BASE_URL": "http://127.0.0.1:8000/v1"}
        with patch.dict("os.environ", env, clear=False):
            config = load_llm_config_from_env(provider="openai", model="gemma4-31b-nvfp4")
            url = openai_compatible_base_url(config)
        self.assertEqual(url, "http://127.0.0.1:8000/v1/chat/completions")

    def test_code2paper_openai_base_url_loopback_is_recognized(self) -> None:
        """``is_loopback_url`` returns True for the canonical endpoint."""

        self.assertTrue(is_loopback_url("http://127.0.0.1:8000/v1"))
        self.assertTrue(is_loopback_url("http://127.0.0.1:8000/v1/chat/completions"))

    def test_code2paper_openai_base_url_no_api_key_required(self) -> None:
        """Loopback deployments do not require an API key."""

        env = {
            "CODE2PAPER_OPENAI_BASE_URL": "http://127.0.0.1:8000/v1",
            # Make sure no API key env vars are set.
            "OPENAI_API_KEY": "",
            "AIHUBMIX_API_KEY": "",
        }
        with patch.dict("os.environ", env, clear=False):
            config = load_llm_config_from_env(provider="openai", model="gemma4-31b-nvfp4")
            self.assertTrue(has_provider_api_key(config))

    def test_code2paper_openai_base_url_with_trailing_slash_normalizes(self) -> None:
        env = {"CODE2PAPER_OPENAI_BASE_URL": "http://127.0.0.1:8000/v1/"}
        with patch.dict("os.environ", env, clear=False):
            config = load_llm_config_from_env(provider="openai", model="gemma4-31b-nvfp4")
            url = openai_compatible_base_url(config)
        self.assertEqual(url, "http://127.0.0.1:8000/v1/chat/completions")

    def test_code2paper_openai_base_url_with_chat_completions_suffix(self) -> None:
        """A URL that already ends in ``/chat/completions`` is left as-is."""

        env = {
            "CODE2PAPER_OPENAI_BASE_URL": "http://127.0.0.1:8000/v1/chat/completions"
        }
        with patch.dict("os.environ", env, clear=False):
            config = load_llm_config_from_env(provider="openai", model="gemma4-31b-nvfp4")
            url = openai_compatible_base_url(config)
        self.assertEqual(url, "http://127.0.0.1:8000/v1/chat/completions")

    def test_aihubmix_base_url_takes_precedence_when_set(self) -> None:
        """``AIHUBMIX_BASE_URL`` wins over ``CODE2PAPER_OPENAI_BASE_URL``."""

        env = {
            "AIHUBMIX_BASE_URL": "http://aihubmix.example.com/v1",
            "CODE2PAPER_OPENAI_BASE_URL": "http://127.0.0.1:8000/v1",
        }
        with patch.dict("os.environ", env, clear=False):
            config = load_llm_config_from_env(provider="openai", model="gemma4-31b-nvfp4")
            url = openai_compatible_base_url(config)
        self.assertEqual(url, "http://aihubmix.example.com/v1/chat/completions")

    def test_default_openai_url_used_when_neither_env_var_set(self) -> None:
        env = {
            "AIHUBMIX_BASE_URL": "",
            "CODE2PAPER_OPENAI_BASE_URL": "",
        }
        with patch.dict("os.environ", env, clear=False):
            config = load_llm_config_from_env(provider="openai", model="gpt-4o")
            url = openai_compatible_base_url(config)
        self.assertEqual(url, "https://api.openai.com/v1/chat/completions")


class PerRoleSamplingEnvVarsTests(unittest.TestCase):
    """Verifies the per-role sampling env vars are loaded into LLMConfig."""

    def test_load_llm_config_reads_top_p(self) -> None:
        with patch.dict("os.environ", {"CODE2PAPER_LLM_TOP_P": "0.9"}, clear=False):
            config = load_llm_config_from_env(provider="openai", model="m")
        self.assertEqual(config.top_p, 0.9)

    def test_load_llm_config_reads_top_k(self) -> None:
        with patch.dict("os.environ", {"CODE2PAPER_LLM_TOP_K": "40"}, clear=False):
            config = load_llm_config_from_env(provider="openai", model="m")
        self.assertEqual(config.top_k, 40)

    def test_load_llm_config_reads_seed(self) -> None:
        with patch.dict("os.environ", {"CODE2PAPER_LLM_SEED": "12345"}, clear=False):
            config = load_llm_config_from_env(provider="openai", model="m")
        self.assertEqual(config.seed, 12345)

    def test_load_llm_config_reads_max_input_tokens(self) -> None:
        with patch.dict("os.environ", {"CODE2PAPER_LLM_MAX_INPUT_TOKENS": "90000"}, clear=False):
            config = load_llm_config_from_env(provider="openai", model="m")
        self.assertEqual(config.max_input_tokens, 90000)

    def test_load_llm_config_reads_role(self) -> None:
        with patch.dict("os.environ", {"CODE2PAPER_LLM_ROLE": "method_writer"}, clear=False):
            config = load_llm_config_from_env(provider="openai", model="m")
        self.assertEqual(config.role, "method_writer")

    def test_load_llm_config_role_kwarg_wins_over_env(self) -> None:
        with patch.dict("os.environ", {"CODE2PAPER_LLM_ROLE": "method_writer"}, clear=False):
            config = load_llm_config_from_env(
                provider="openai", model="m", role="research_supervisor"
            )
        self.assertEqual(config.role, "research_supervisor")

    def test_load_llm_config_top_p_unset_returns_none(self) -> None:
        with patch.dict("os.environ", {"CODE2PAPER_LLM_TOP_P": ""}, clear=False):
            config = load_llm_config_from_env(provider="openai", model="m")
        self.assertIsNone(config.top_p)

    def test_load_llm_config_top_k_unset_returns_none(self) -> None:
        with patch.dict("os.environ", {"CODE2PAPER_LLM_TOP_K": ""}, clear=False):
            config = load_llm_config_from_env(provider="openai", model="m")
        self.assertIsNone(config.top_k)

    def test_load_llm_config_seed_unset_returns_none(self) -> None:
        with patch.dict("os.environ", {"CODE2PAPER_LLM_SEED": ""}, clear=False):
            config = load_llm_config_from_env(provider="openai", model="m")
        self.assertIsNone(config.seed)

    def test_load_llm_config_max_input_tokens_unset_returns_none(self) -> None:
        with patch.dict("os.environ", {"CODE2PAPER_LLM_MAX_INPUT_TOKENS": ""}, clear=False):
            config = load_llm_config_from_env(provider="openai", model="m")
        self.assertIsNone(config.max_input_tokens)

    def test_load_llm_config_top_p_invalid_returns_none(self) -> None:
        with patch.dict("os.environ", {"CODE2PAPER_LLM_TOP_P": "not-a-number"}, clear=False):
            config = load_llm_config_from_env(provider="openai", model="m")
        self.assertIsNone(config.top_p)

    def test_load_llm_config_top_k_invalid_returns_none(self) -> None:
        with patch.dict("os.environ", {"CODE2PAPER_LLM_TOP_K": "not-a-number"}, clear=False):
            config = load_llm_config_from_env(provider="openai", model="m")
        self.assertIsNone(config.top_k)

    def test_load_llm_config_top_p_top_k_seed_zero_is_valid(self) -> None:
        """``0`` is a valid value for top_p / top_k / seed (distinct from unset)."""

        env = {
            "CODE2PAPER_LLM_TOP_P": "0.0",
            "CODE2PAPER_LLM_TOP_K": "0",
            "CODE2PAPER_LLM_SEED": "0",
        }
        with patch.dict("os.environ", env, clear=False):
            config = load_llm_config_from_env(provider="openai", model="m")
        self.assertEqual(config.top_p, 0.0)
        self.assertEqual(config.top_k, 0)
        self.assertEqual(config.seed, 0)

    def test_load_llm_config_max_input_tokens_zero_is_rejected_by_schema(self) -> None:
        """``max_input_tokens=0`` is invalid (schema requires ``>= 1``)."""

        env = {"CODE2PAPER_LLM_MAX_INPUT_TOKENS": "0"}
        with patch.dict("os.environ", env, clear=False):
            with self.assertRaises(Exception):
                load_llm_config_from_env(provider="openai", model="m")


if __name__ == "__main__":
    unittest.main()
