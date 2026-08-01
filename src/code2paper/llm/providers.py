"""Provider configuration helpers for LLM-backed phases."""

from __future__ import annotations

import os

from code2paper.schemas import LLMConfig, LLMProvider
from code2paper.llm.capabilities import is_loopback_url


# Public defaults live here so every CLI resolves presets from one authority.
DEFAULT_TEXT_MODEL = "gpt-4.1-mini"
DEFAULT_FIGURE_IMAGE_MODEL = "aihubmix/chat-image-2.0"


_STRICT_JSON_DEFAULT_MODEL_BY_PROVIDER: dict[LLMProvider, str] = {
    LLMProvider.OPENAI: DEFAULT_TEXT_MODEL,
}


def load_llm_config_from_env(
    *,
    provider: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_output_tokens: int | None = None,
    reasoning_effort: str | None = None,
    thinking_token_budget: int | None = None,
    prompt_template_version: str | None = None,
    role: str | None = None,
) -> LLMConfig:
    provider_value = _normalize_provider_alias(provider or os.environ.get("CODE2PAPER_LLM_PROVIDER", "none"))
    provider_enum = LLMProvider(provider_value)
    model_value = model or os.environ.get("CODE2PAPER_LLM_MODEL", "")
    if not model_value:
        model_value = _default_model_for_provider(provider_enum)
    if _bool_env("CODE2PAPER_ENFORCE_STRICT_JSON_MODEL", False):
        model_value = _resolved_strict_model(provider=provider_enum, current=model_value)
    temperature_value = temperature
    if temperature_value is None:
        temperature_value = _float_env("CODE2PAPER_LLM_TEMPERATURE", 0.2)
    max_tokens_value = max_output_tokens
    if max_tokens_value is None:
        max_tokens_value = _int_env("CODE2PAPER_LLM_MAX_OUTPUT_TOKENS", 12000)
    reasoning_effort_value = (
        reasoning_effort
        if reasoning_effort is not None
        else os.environ.get("CODE2PAPER_LLM_REASONING_EFFORT", "")
    ).strip()
    thinking_token_budget_value = thinking_token_budget
    if thinking_token_budget_value is None:
        thinking_token_budget_value = _int_env_or_none(
            "CODE2PAPER_LLM_THINKING_TOKEN_BUDGET"
        )
    top_p_value = _float_env_or_none("CODE2PAPER_LLM_TOP_P")
    top_k_value = _int_env_or_none("CODE2PAPER_LLM_TOP_K")
    seed_value = _int_env_or_none("CODE2PAPER_LLM_SEED")
    max_input_tokens_value = _int_env_or_none("CODE2PAPER_LLM_MAX_INPUT_TOKENS")
    role_value = role or os.environ.get("CODE2PAPER_LLM_ROLE", "")
    return LLMConfig(
        provider=provider_enum,
        model=model_value,
        temperature=temperature_value,
        max_output_tokens=max_tokens_value,
        reasoning_effort=reasoning_effort_value,
        thinking_token_budget=thinking_token_budget_value,
        request_timeout_seconds=_int_env("CODE2PAPER_LLM_TIMEOUT_SECONDS", 300),
        retry_max_attempts=_int_env("CODE2PAPER_LLM_RETRY_MAX_ATTEMPTS", 5),
        retry_initial_delay_seconds=_float_env("CODE2PAPER_LLM_RETRY_INITIAL_DELAY_SECONDS", 2.0),
        retry_backoff_multiplier=_float_env("CODE2PAPER_LLM_RETRY_BACKOFF_MULTIPLIER", 2.0),
        fail_on_timeout=_bool_env("CODE2PAPER_FAIL_ON_TIMEOUT", True),
        prompt_template_version=prompt_template_version
        or os.environ.get("CODE2PAPER_PROMPT_TEMPLATE_VERSION", ""),
        require_api_for_writing=_bool_env("CODE2PAPER_REQUIRE_API_FOR_WRITING", True),
        cache=_bool_env("CODE2PAPER_LLM_CACHE", True),
        role=role_value,
        top_p=top_p_value,
        top_k=top_k_value,
        seed=seed_value,
        max_input_tokens=max_input_tokens_value,
    )


def with_node_output_budget(config: LLMConfig, node: str, default: int) -> LLMConfig:
    """Clamp a call family to its own audited output-token budget."""
    env_name = "CODE2PAPER_" + node.upper().replace("-", "_") + "_MAX_OUTPUT_TOKENS"
    requested = _int_env(env_name, default)
    return config.model_copy(update={"max_output_tokens": max(1, min(config.max_output_tokens, requested))})


def provider_api_key_env(provider: LLMProvider) -> str:
    envs = provider_api_key_env_candidates(provider)
    return envs[0] if envs else ""


def provider_api_key_env_candidates(provider: LLMProvider) -> list[str]:
    provider_value = getattr(provider, "value", str(provider))
    if provider_value == "openai":
        # AIHUBMIX is OpenAI-compatible; many setups use AIHUBMIX_API_KEY.
        return ["OPENAI_API_KEY", "AIHUBMIX_API_KEY"]
    if provider_value == "anthropic":
        return ["ANTHROPIC_API_KEY"]
    if provider_value == "google":
        return ["GOOGLE_API_KEY"]
    if provider_value == "openrouter":
        return ["OPENROUTER_API_KEY"]
    return []


def has_provider_api_key(config: LLMConfig) -> bool:
    env_names = provider_api_key_env_candidates(config.provider)
    if any(os.environ.get(env_name) for env_name in env_names):
        return True
    provider_value = getattr(config.provider, "value", str(config.provider))
    return provider_value == "openai" and is_loopback_url(openai_compatible_base_url(config))


def openai_compatible_base_url(config: LLMConfig) -> str:
    provider_value = getattr(config.provider, "value", str(config.provider))
    if provider_value == "openrouter":
        raw = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1/chat/completions")
        return _normalize_openai_chat_completions_url(raw)
    if provider_value == "openai":
        raw = (
            os.environ.get("AIHUBMIX_BASE_URL")
            or os.environ.get("CODE2PAPER_OPENAI_BASE_URL")
            or "https://api.openai.com/v1/chat/completions"
        )
        return _normalize_openai_chat_completions_url(raw)
    return ""


def _normalize_openai_chat_completions_url(raw: str) -> str:
    base = (raw or "").strip().rstrip("/")
    if not base:
        return "https://api.openai.com/v1/chat/completions"
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    if base.endswith("/v1/"):
        return f"{base.rstrip('/')}/chat/completions"
    return f"{base}/v1/chat/completions"


def _float_env(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _float_env_or_none(name: str) -> float | None:
    """Read a float env var; return ``None`` when unset or empty.

    Used for optional sampling fields (``top_p``, etc.) where ``None``
    means "provider default" rather than "0.0".
    """

    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _int_env_or_none(name: str) -> int | None:
    """Read an int env var; return ``None`` when unset or empty."""

    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _normalize_provider_alias(value: str) -> str:
    lowered = (value or "").strip().lower()
    aliases = {
        "moonshot": "openai",
        "aihubmix": "openai",
        "kimi": "openai",
    }
    return aliases.get(lowered, lowered or "none")


def _default_model_for_provider(provider: LLMProvider) -> str:
    return os.environ.get("CODE2PAPER_DEFAULT_LLM_MODEL", "") or _STRICT_JSON_DEFAULT_MODEL_BY_PROVIDER.get(provider, "")


def _resolved_strict_model(*, provider: LLMProvider, current: str) -> str:
    strict_model = os.environ.get("CODE2PAPER_STRICT_JSON_MODEL", "") or _STRICT_JSON_DEFAULT_MODEL_BY_PROVIDER.get(provider, "")
    if provider != LLMProvider.OPENAI:
        return current or strict_model
    lowered = (current or "").lower()
    if lowered and not any(token in lowered for token in ("qwen", "kimi", "glm", "deepseek")):
        return current
    return strict_model or current
