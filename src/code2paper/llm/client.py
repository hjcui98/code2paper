"""Small LLM client abstraction for structured code2paper calls.

The client intentionally uses the Python standard library instead of provider
SDKs. That keeps inspect-only runs dependency-light while still allowing real
provider calls when API keys are configured.
"""

from __future__ import annotations

from dataclasses import dataclass
import http.client
import json
import os
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path

from code2paper.export.run_manifest import hash_json_payload, hash_text
from code2paper.llm.providers import (
    has_provider_api_key,
    openai_compatible_base_url,
    provider_api_key_env,
    provider_api_key_env_candidates,
)
from code2paper.llm.capabilities import LLMCapabilityProfile, StructuredResponseMode, is_loopback_url, load_capability_profile
from code2paper.llm.retry_policy import RetryPolicy
from code2paper.schemas import LLMConfig, LLMProvider


@dataclass(frozen=True)
class LLMRequest:
    prompt_template_id: str
    prompt: str
    input_payload: object
    schema_name: str = ""
    response_json_schema: dict | None = None

    @property
    def input_hash(self) -> str:
        return hash_json_payload(
            {
                "prompt_template_id": self.prompt_template_id,
                "prompt": self.prompt,
                "input_payload": self.input_payload,
                "schema_name": self.schema_name,
                "response_json_schema": self.response_json_schema or {},
            }
        )


@dataclass(frozen=True)
class LLMResponse:
    text: str
    response_hash: str
    blocked_reason: str = ""
    cached: bool = False
    response_mode: str = ""
    finish_reason: str = ""
    token_usage: dict[str, int] | None = None


@dataclass(frozen=True)
class _ProviderResult:
    text: str
    response_mode: str = ""
    finish_reason: str = ""
    token_usage: dict[str, int] | None = None


class LLMClient:
    def __init__(self, config: LLMConfig, capability_profile: LLMCapabilityProfile | None = None) -> None:
        self.config = config
        self.capability_profile = capability_profile or load_capability_profile(
            provider=getattr(config.provider, "value", str(config.provider)), model=config.model
        )

    def complete(self, request: LLMRequest, *, dry_run: bool = False) -> LLMResponse:
        if dry_run:
            return LLMResponse(
                text="",
                response_hash=hash_text(""),
                blocked_reason="dry_run",
            )
        if self.config.cache:
            cached_text = _read_cache(self.config, request)
            if cached_text is not None:
                return LLMResponse(
                    text=cached_text,
                    response_hash=hash_text(cached_text),
                    cached=True,
                )
        if self.config.provider.value == "none":
            return LLMResponse(
                text="",
                response_hash=hash_text(""),
                blocked_reason="llm_provider_not_configured",
            )
        if not has_provider_api_key(self.config):
            return LLMResponse(
                text="",
                response_hash=hash_text(""),
                blocked_reason="llm_api_key_missing",
            )
        try:
            result = self._complete_provider_with_semantic_retry(request)
        except ProviderTimeoutError as exc:
            if self.config.fail_on_timeout:
                raise
            return LLMResponse(text="", response_hash=hash_text(""), blocked_reason=str(exc))
        except ProviderRuntimeError as exc:
            return LLMResponse(text="", response_hash=hash_text(""), blocked_reason=str(exc))
        if self.config.cache:
            _write_cache(self.config, request, result.text)
        return LLMResponse(
            text=result.text,
            response_hash=hash_text(result.text),
            response_mode=result.response_mode,
            finish_reason=result.finish_reason,
            token_usage=result.token_usage,
        )

    def _complete_provider_with_semantic_retry(self, request: LLMRequest) -> _ProviderResult:
        retry_policy = _retry_policy(self.config)
        delay_seconds = max(0.0, retry_policy.initial_delay_seconds)
        attempts = max(1, retry_policy.max_attempts)
        last_error: ProviderRuntimeError | None = None
        for attempt in range(1, attempts + 1):
            result = self._complete_provider(request)
            if result.text.strip():
                return result
            last_error = ProviderRuntimeError("provider_response_empty_content")
            if attempt < attempts and delay_seconds > 0:
                time.sleep(delay_seconds)
                delay_seconds *= max(1.0, retry_policy.backoff_multiplier)
        if last_error is not None:
            raise last_error
        raise ProviderRuntimeError("provider_response_empty_content")

    def _complete_provider(self, request: LLMRequest) -> _ProviderResult:
        provider_value = getattr(self.config.provider, "value", str(self.config.provider))
        if provider_value in {"openai", "openrouter"}:
            return self._complete_openai_compatible(request)
        if provider_value == "anthropic":
            return self._complete_anthropic(request)
        if provider_value == "google":
            return self._complete_google(request)
        raise ProviderRuntimeError(f"unsupported_provider:{provider_value}")

    def _complete_openai_compatible(self, request: LLMRequest) -> _ProviderResult:
        base_url = openai_compatible_base_url(self.config)
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": request.prompt},
                {"role": "user", "content": _json_dumps(request.input_payload)},
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_output_tokens,
        }
        response_mode = self.capability_profile.response_mode
        if request.response_json_schema and response_mode == StructuredResponseMode.NATIVE_JSON_SCHEMA:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": _schema_name(request),
                    "schema": request.response_json_schema,
                    "strict": True,
                },
            }
        elif request.response_json_schema and response_mode == StructuredResponseMode.JSON_OBJECT:
            payload["response_format"] = {"type": "json_object"}
            payload["messages"][0]["content"] += "\nReturn JSON matching this schema:\n" + _json_dumps(request.response_json_schema)
        elif request.response_json_schema:
            payload["messages"][0]["content"] += "\nReturn only JSON matching this schema:\n" + _json_dumps(request.response_json_schema)
        response = _post_json(
            base_url,
            payload,
            headers=_auth_headers(self.config.provider, self.config),
            timeout_seconds=self.config.request_timeout_seconds,
            retry_policy=_retry_policy(self.config),
        )
        try:
            choice = response["choices"][0]
            return _ProviderResult(
                text=choice["message"]["content"],
                response_mode=response_mode.value,
                finish_reason=str(choice.get("finish_reason", "")),
                token_usage=_normalized_usage(response.get("usage")),
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderRuntimeError("provider_response_missing_content") from exc

    def _complete_anthropic(self, request: LLMRequest) -> _ProviderResult:
        response_schema_note = ""
        if request.response_json_schema:
            response_schema_note = "\nReturn only JSON matching this schema:\n" + _json_dumps(
                request.response_json_schema
            )
        payload = {
            "model": self.config.model,
            "max_tokens": self.config.max_output_tokens,
            "temperature": self.config.temperature,
            "system": request.prompt + response_schema_note,
            "messages": [{"role": "user", "content": _json_dumps(request.input_payload)}],
        }
        response = _post_json(
            "https://api.anthropic.com/v1/messages",
            payload,
            headers={
                **_auth_headers(self.config.provider, self.config),
                "anthropic-version": "2023-06-01",
            },
            timeout_seconds=self.config.request_timeout_seconds,
            retry_policy=_retry_policy(self.config),
        )
        try:
            blocks = response["content"]
            return _ProviderResult(
                text="".join(block.get("text", "") for block in blocks if block.get("type") == "text"),
                response_mode=StructuredResponseMode.PROMPT_ONLY.value,
                finish_reason=str(response.get("stop_reason", "")),
                token_usage=_normalized_usage(response.get("usage")),
            )
        except (KeyError, TypeError) as exc:
            raise ProviderRuntimeError("provider_response_missing_content") from exc

    def _complete_google(self, request: LLMRequest) -> _ProviderResult:
        api_key = _api_key(self.config.provider, self.config)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.config.model}:generateContent?key={api_key}"
        generation_config = {
            "temperature": self.config.temperature,
            "maxOutputTokens": self.config.max_output_tokens,
            "responseMimeType": "application/json",
        }
        if request.response_json_schema:
            generation_config["responseSchema"] = request.response_json_schema
        payload = {
            "systemInstruction": {"parts": [{"text": request.prompt}]},
            "contents": [{"role": "user", "parts": [{"text": _json_dumps(request.input_payload)}]}],
            "generationConfig": generation_config,
        }
        response = _post_json(
            url,
            payload,
            headers={"Content-Type": "application/json"},
            timeout_seconds=self.config.request_timeout_seconds,
            retry_policy=_retry_policy(self.config),
        )
        try:
            parts = response["candidates"][0]["content"]["parts"]
            candidate = response["candidates"][0]
            return _ProviderResult(
                text="".join(part.get("text", "") for part in parts),
                response_mode=StructuredResponseMode.NATIVE_JSON_SCHEMA.value if request.response_json_schema else "",
                finish_reason=str(candidate.get("finishReason", "")),
                token_usage=_normalized_usage(response.get("usageMetadata")),
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderRuntimeError("provider_response_missing_content") from exc


class ProviderRuntimeError(RuntimeError):
    pass


class ProviderTimeoutError(ProviderRuntimeError):
    pass


def _post_json(
    url: str,
    payload: dict,
    *,
    headers: dict[str, str],
    timeout_seconds: int,
    retry_policy: RetryPolicy,
) -> dict:
    delay_seconds = max(0.0, retry_policy.initial_delay_seconds)
    attempts = max(1, retry_policy.max_attempts)
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(
            url,
            data=_json_dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                body = response.read().decode("utf-8")
            try:
                return json.loads(body)
            except json.JSONDecodeError as exc:
                raise ProviderRuntimeError("provider_response_not_json") from exc
        except http.client.IncompleteRead as exc:
            partial_len = len(exc.partial or b"")
            last_error = ProviderRuntimeError(f"provider_network_error:incomplete_read:{partial_len}")
            if attempt >= attempts:
                raise last_error from exc
        except http.client.HTTPException as exc:
            last_error = ProviderRuntimeError(f"provider_network_error:http_exception:{exc.__class__.__name__}")
            if attempt >= attempts:
                raise last_error from exc
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            last_error = ProviderRuntimeError(f"provider_http_error:{exc.code}:{detail}")
            if exc.code not in {408, 409, 429, 500, 502, 503, 504} or attempt >= attempts:
                raise last_error from exc
        except urllib.error.URLError as exc:
            last_error = ProviderRuntimeError(f"provider_network_error:{exc.reason}")
            if attempt >= attempts:
                raise last_error from exc
        except (TimeoutError, socket.timeout) as exc:
            last_error = ProviderTimeoutError("provider_timeout_error:read_timeout")
            if attempt >= attempts:
                raise last_error from exc
        except OSError as exc:
            lowered = str(exc).lower()
            if "timed out" in lowered:
                last_error = ProviderTimeoutError("provider_timeout_error:read_timeout")
                if attempt >= attempts:
                    raise last_error from exc
            elif any(
                token in lowered
                for token in (
                    "connection reset",
                    "connection aborted",
                    "broken pipe",
                    "network is unreachable",
                    "temporarily unavailable",
                )
            ):
                last_error = ProviderRuntimeError(f"provider_network_error:oserror:{exc.__class__.__name__}")
                if attempt >= attempts:
                    raise last_error from exc
            else:
                raise
        if attempt < attempts and delay_seconds > 0:
            time.sleep(delay_seconds)
            delay_seconds *= max(1.0, retry_policy.backoff_multiplier)
    if last_error is not None:
        raise last_error
    raise ProviderRuntimeError("provider_unknown_error")


def _auth_headers(provider: LLMProvider, config: LLMConfig) -> dict[str, str]:
    provider_value = getattr(provider, "value", str(provider))
    if provider_value in {"openai", "openrouter"}:
        return {"Authorization": f"Bearer {_api_key(provider, config)}"}
    if provider_value == "anthropic":
        return {"x-api-key": _api_key(provider, config)}
    return {}


def _api_key(provider: LLMProvider, config: LLMConfig) -> str:
    for env_name in provider_api_key_env_candidates(provider):
        value = os.environ.get(env_name, "")
        if value:
            return value
    # Fallback to legacy single-env lookup for compatibility.
    env_name = provider_api_key_env(provider)
    value = os.environ.get(env_name, "")
    if value:
        return value
    if getattr(provider, "value", str(provider)) == "openai" and is_loopback_url(openai_compatible_base_url(config)):
        return "dummy-local-vllm"
    raise ProviderRuntimeError("llm_api_key_missing")


def _normalized_usage(value: object) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    normalized: dict[str, int] = {}
    for key, item in value.items():
        if isinstance(item, int) and not isinstance(item, bool):
            normalized[str(key)] = item
    return normalized or None


def _schema_name(request: LLMRequest) -> str:
    name = request.schema_name or "structured_response"
    return "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in name)


def _json_dumps(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _retry_policy(config: LLMConfig) -> RetryPolicy:
    return RetryPolicy(
        max_attempts=max(1, config.retry_max_attempts),
        initial_delay_seconds=max(0.0, config.retry_initial_delay_seconds),
        backoff_multiplier=max(1.0, config.retry_backoff_multiplier),
    )


def _cache_key(config: LLMConfig, request: LLMRequest) -> str:
    return hash_text(
        json.dumps(
            {
                "provider": config.provider.value,
                "model": config.model,
                "temperature": config.temperature,
                "max_output_tokens": config.max_output_tokens,
                "request_input_hash": request.input_hash,
            },
            sort_keys=True,
        )
    ).replace("sha256:", "")


def _cache_dir() -> Path:
    root = os.environ.get("CODE2PAPER_LLM_CACHE_DIR", "/tmp/code2paper_llm_cache")
    return Path(root)


def _read_cache(config: LLMConfig, request: LLMRequest) -> str | None:
    path = _cache_dir() / f"{_cache_key(config, request)}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    text = payload.get("text")
    if not isinstance(text, str):
        return None
    return text


def _write_cache(config: LLMConfig, request: LLMRequest, text: str) -> None:
    path = _cache_dir() / f"{_cache_key(config, request)}.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _json_dumps(
                {
                    "provider": config.provider.value,
                    "model": config.model,
                    "request_input_hash": request.input_hash,
                    "text": text,
                }
            ),
            encoding="utf-8",
        )
    except OSError:
        return
