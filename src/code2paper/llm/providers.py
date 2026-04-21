"""Provider configuration helpers for LLM-backed phases."""

from __future__ import annotations

import os

from code2paper.schemas import LLMConfig, LLMProvider


_STRICT_JSON_DEFAULT_MODEL_BY_PROVIDER: dict[LLMProvider, str] = {
    LLMProvider.OPENAI: "gpt-4.1-mini",
}


def load_llm_config_from_env(
    *,
    provider: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_output_tokens: int | None = None,
    prompt_template_version: str | None = None,
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
    return LLMConfig(
        provider=provider_enum,
        model=model_value,
        temperature=temperature_value,
        max_output_tokens=max_tokens_value,
        request_timeout_seconds=_int_env("CODE2PAPER_LLM_TIMEOUT_SECONDS", 300),
        retry_max_attempts=_int_env("CODE2PAPER_LLM_RETRY_MAX_ATTEMPTS", 5),
        retry_initial_delay_seconds=_float_env("CODE2PAPER_LLM_RETRY_INITIAL_DELAY_SECONDS", 2.0),
        retry_backoff_multiplier=_float_env("CODE2PAPER_LLM_RETRY_BACKOFF_MULTIPLIER", 2.0),
        fail_on_timeout=_bool_env("CODE2PAPER_FAIL_ON_TIMEOUT", True),
        prompt_template_version=prompt_template_version
        or os.environ.get("CODE2PAPER_PROMPT_TEMPLATE_VERSION", ""),
        require_api_for_writing=_bool_env("CODE2PAPER_REQUIRE_API_FOR_WRITING", True),
        cache=_bool_env("CODE2PAPER_LLM_CACHE", True),
    )


def provider_api_key_env(provider: LLMProvider) -> str:
    envs = provider_api_key_env_candidates(provider)
    return envs[0] if envs else ""


def provider_api_key_env_candidates(provider: LLMProvider) -> list[str]:
    if provider == LLMProvider.OPENAI:
        # AIHUBMIX is OpenAI-compatible; many setups use AIHUBMIX_API_KEY.
        return ["OPENAI_API_KEY", "AIHUBMIX_API_KEY"]
    if provider == LLMProvider.ANTHROPIC:
        return ["ANTHROPIC_API_KEY"]
    if provider == LLMProvider.GOOGLE:
        return ["GOOGLE_API_KEY"]
    if provider == LLMProvider.OPENROUTER:
        return ["OPENROUTER_API_KEY"]
    return []


def has_provider_api_key(config: LLMConfig) -> bool:
    env_names = provider_api_key_env_candidates(config.provider)
    return any(os.environ.get(env_name) for env_name in env_names)


def openai_compatible_base_url(config: LLMConfig) -> str:
    if config.provider == LLMProvider.OPENROUTER:
        raw = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1/chat/completions")
        return _normalize_openai_chat_completions_url(raw)
    if config.provider == LLMProvider.OPENAI:
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
