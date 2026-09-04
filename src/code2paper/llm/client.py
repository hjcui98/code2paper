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
import tempfile
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

_STREAM_METRICS: dict[str, object] = {
    "usage": None,
    "thinking_chars": 0,
    "finish_reason": "",
}


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
    # Optional in-process structured payload retained by publication writers
    # for semantic transaction comparison.  It is never serialized into the
    # provider cache or emitted as reader-facing prose.
    metadata: object | None = None


@dataclass(frozen=True)
class _ProviderResult:
    text: str | None
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
        response = self._complete(request, dry_run=dry_run)
        # Import lazily to avoid the generation-trace module's intentional
        # dependency on LLMRequest/LLMResponse creating an import cycle.
        from code2paper.llm.generation_trace import (
            build_generation_call_trace,
            record_run_generation_trace,
        )

        trace = build_generation_call_trace(
            call_id=f"{request.prompt_template_id}:{request.input_hash[7:19]}",
            config=self.config,
            request=request,
            response=response,
        )
        record_run_generation_trace(trace)
        return response

    def _complete(self, request: LLMRequest, *, dry_run: bool = False) -> LLMResponse:
        if dry_run:
            return LLMResponse(
                text="",
                response_hash=hash_text(""),
                blocked_reason="dry_run",
            )
        if self.config.cache:
            cached_result = _read_cache(self.config, request, self.capability_profile)
            if cached_result is not None:
                return LLMResponse(
                    text=cached_result.text,
                    response_hash=hash_text(cached_result.text),
                    cached=True,
                    response_mode=cached_result.response_mode,
                    finish_reason=cached_result.finish_reason,
                    token_usage=cached_result.token_usage,
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
            _write_cache(self.config, request, self.capability_profile, result)
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
            if result.text is not None and result.text.strip():
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
        # Per-role sampling fields (Phase 1 R8 config basis).  Only
        # include fields the caller actually set (None means "use the
        # provider default"); sending e.g. ``top_p: null`` would
        # override the vLLM default on some backends.
        if self.config.top_p is not None:
            payload["top_p"] = self.config.top_p
        if self.config.top_k is not None:
            payload["top_k"] = self.config.top_k
        if self.config.seed is not None:
            payload["seed"] = self.config.seed
        # ``reasoning_effort`` is supported by OpenAI reasoning models and
        # by recent OpenAI-compatible vLLM servers.  In vLLM,
        # ``reasoning_effort="none"`` maps to
        # ``chat_template_kwargs.enable_thinking=false``.  Only send the
        # field when explicitly configured so providers that do not support
        # reasoning controls retain their existing request shape.
        if self.config.reasoning_effort:
            payload["reasoning_effort"] = self.config.reasoning_effort
        # Local vLLM deployments do not all apply ``reasoning_effort=none``
        # consistently when a long structured prompt is used.  Make the chat
        # template choice explicit for loopback endpoints so Qwen writes the
        # structured answer to ``message.content`` instead of ending after a
        # reasoning-only turn.  Keep remote provider request shapes unchanged.
        if self.config.reasoning_effort == "none" and is_loopback_url(base_url):
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        # Recent vLLM OpenAI-compatible servers expose a separate thinking
        # budget.  At the limit the sampler forces the model's end-of-thinking
        # token, leaving the remainder of ``max_tokens`` for the answer.
        # This is an opt-in extension: omit it for providers that implement
        # only the standard OpenAI request shape.
        if self.config.thinking_token_budget is not None:
            payload["thinking_token_budget"] = self.config.thinking_token_budget
        configured_response_mode = self.capability_profile.response_mode
        response_mode = (
            configured_response_mode
            if request.response_json_schema
            else StructuredResponseMode.PROMPT_ONLY
        )
        if (
            request.response_json_schema
            and configured_response_mode == StructuredResponseMode.NATIVE_JSON_SCHEMA
        ):
            # Loopback vLLM deployments use xgrammar for guided decoding, which
            # rejects the ``uniqueItems`` keyword that the publication writer
            # emits for callback-required sections.  ``uniqueItems`` is a
            # grammar hint only; the binding/authorship gate already enforces
            # identifier uniqueness, so stripping it for loopback endpoints does
            # not weaken the contract and preserves the ``enum``/``const``
            # enforcement that prevents representation errors (e.g. field names
            # emitted as claim ids).  Remote provider schemas are unchanged.
            schema_to_send = request.response_json_schema
            if is_loopback_url(base_url):
                schema_to_send = _strip_unique_items(schema_to_send)
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": _schema_name(request),
                    "schema": schema_to_send,
                    "strict": True,
                },
            }
        elif (
            request.response_json_schema
            and configured_response_mode == StructuredResponseMode.JSON_OBJECT
        ):
            payload["response_format"] = {"type": "json_object"}
            payload["messages"][0]["content"] += "\nReturn JSON matching this schema:\n" + _json_dumps(request.response_json_schema)
        elif request.response_json_schema:
            payload["messages"][0]["content"] += "\nReturn only JSON matching this schema:\n" + _json_dumps(request.response_json_schema)
        if (
            request.response_json_schema
            and response_mode in {
                StructuredResponseMode.NATIVE_JSON_SCHEMA,
                StructuredResponseMode.JSON_OBJECT,
            }
            and is_loopback_url(base_url)
            and os.environ.get("CODE2PAPER_LLM_STREAM_STRUCTURED", "").strip().lower()
            in {"1", "true", "yes", "on"}
        ):
            payload["stream"] = True
            payload["stream_options"] = {"include_usage": True}
            text = _post_openai_stream_until_complete_json(
                base_url,
                payload,
                headers=_auth_headers(self.config.provider, self.config),
                timeout_seconds=self.config.request_timeout_seconds,
                retry_policy=_retry_policy(self.config),
            )
            return _ProviderResult(
                text=text,
                response_mode=response_mode.value,
                finish_reason="structured_complete",
                token_usage=_normalized_usage(_STREAM_METRICS.get("usage")),
            )
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
            headers={
                "Content-Type": "application/json",
                "User-Agent": _CLIENT_USER_AGENT,
                **headers,
            },
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


def _post_openai_stream_until_complete_json(
    url: str,
    payload: dict,
    *,
    headers: dict[str, str],
    timeout_seconds: int,
    retry_policy: RetryPolicy,
) -> str:
    """Read an OpenAI SSE stream through its terminal usage event.

    Some local guided-decoding stacks repeat an already complete JSON object
    instead of emitting EOS. Once the first balanced outer value is observed,
    preserve it and stop accumulating repeated content while draining the
    terminal usage event.  This keeps the model-authored response bounded and
    records both prompt and completion token counts when the provider emits
    OpenAI-compatible streaming usage.
    """

    delay_seconds = max(0.0, retry_policy.initial_delay_seconds)
    attempts = max(1, retry_policy.max_attempts)
    last_error: Exception | None = None
    _STREAM_METRICS["usage"] = None
    _STREAM_METRICS["thinking_chars"] = 0
    _STREAM_METRICS["finish_reason"] = ""
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(
            url,
            data=_json_dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        try:
            accumulated = ""
            complete_text: str | None = None
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                iterator = iter(response)
                last_content_at = time.monotonic()
                received_progress = False
                while True:
                    inactivity_limit = min(timeout_seconds, 30 if received_progress else 120)
                    inactivity_remaining = inactivity_limit - (
                        time.monotonic() - last_content_at
                    )
                    if inactivity_remaining <= 0:
                        if complete_text is not None:
                            return complete_text
                        complete = _first_complete_json(accumulated)
                        if complete is not None:
                            return complete
                        raise ProviderTimeoutError(
                            "provider_timeout_error:stream_inactivity"
                        )
                    # HTTPResponse uses a BufferedReader.  Selecting on its
                    # raw socket can report "not ready" after urllib has
                    # already prefetched the next SSE line (including [DONE])
                    # into the Python buffer, causing a false 30--120 second
                    # hang after the server has completed.  Let readline
                    # consume buffered bytes first and bound an actual socket
                    # read with the inactivity deadline.
                    if _set_response_read_timeout(response, inactivity_remaining):
                        try:
                            raw_line = response.readline()
                        except (TimeoutError, socket.timeout):
                            complete = _first_complete_json(accumulated)
                            if complete is not None:
                                return complete
                            raise ProviderTimeoutError(
                                "provider_timeout_error:stream_inactivity"
                            )
                        if not raw_line:
                            break
                    else:
                        try:
                            raw_line = next(iterator)
                        except StopIteration:
                            break
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data:
                        continue
                    if data == "[DONE]":
                        if complete_text is not None:
                            return complete_text
                        complete = _first_complete_json(accumulated)
                        if complete is not None:
                            return complete
                        if accumulated.strip():
                            # The owning structured-response layer may apply a
                            # representation-only suffix repair.  [DONE] is a
                            # protocol terminal marker; waiting for another
                            # byte on a keep-alive socket can only hang.
                            return accumulated
                        raise ProviderRuntimeError(
                            "provider_stream_done_without_json_content"
                        )
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    usage = event.get("usage")
                    if isinstance(usage, dict):
                        _STREAM_METRICS["usage"] = usage
                    try:
                        choice = (event.get("choices") or [None])[0] or {}
                        delta = choice.get("delta") or {}
                    except (KeyError, IndexError, TypeError):
                        continue
                    finish_reason = choice.get("finish_reason")
                    if finish_reason:
                        _STREAM_METRICS["finish_reason"] = str(finish_reason)
                    content = delta.get("content")
                    reasoning_content = delta.get("reasoning_content")
                    if isinstance(reasoning_content, str) and reasoning_content:
                        _STREAM_METRICS["thinking_chars"] = int(
                            _STREAM_METRICS.get("thinking_chars") or 0
                        ) + len(reasoning_content)
                        last_content_at = time.monotonic()
                        received_progress = True
                    if isinstance(content, str):
                        if content:
                            last_content_at = time.monotonic()
                            received_progress = True
                        if complete_text is None:
                            accumulated += content
                            complete = _first_complete_json(accumulated)
                            if complete is not None:
                                # The usage-only SSE event is normally emitted
                                # after the final choice event.  Keep draining
                                # the stream after the first complete JSON value,
                                # but stop accumulating repeated/padded content.
                                complete_text = complete
                            if complete_text is None and _incomplete_json_has_whitespace_padding(accumulated):
                                # Guided decoding on this local stack sometimes
                                # stops mid-string and then pads the rest of
                                # max_tokens with newlines (finish_reason still
                                # looks complete).  Close the stream so the GPU
                                # does not spend a full role budget on padding;
                                # the owning parser still fail-closes.
                                return accumulated
                    if finish_reason:
                        if complete_text is not None:
                            # Do not return before the usage-only terminal
                            # event; it carries both prompt and completion
                            # token counts on vLLM/OpenAI-compatible streams.
                            continue
                        complete = _first_complete_json(accumulated)
                        if complete is not None:
                            return complete
                        # The provider finished the stream before a complete
                        # JSON value arrived.  Preserve the model's own bytes
                        # instead of discarding them: the writer's recovery
                        # layer may close an unambiguous container suffix
                        # (representation-only repair).  Only a truly empty
                        # accumulation is a hard transport failure.
                        if accumulated.strip():
                            return accumulated
                        raise ProviderRuntimeError(
                            "provider_stream_finished_before_complete_json"
                        )
            if complete_text is not None:
                return complete_text
            complete = _first_complete_json(accumulated)
            if complete is not None:
                return complete
            if accumulated.strip():
                return accumulated
            last_error = ProviderRuntimeError("provider_stream_ended_before_complete_json")
            if attempt >= attempts:
                raise last_error
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
            if complete_text is not None:
                return complete_text
            complete = _first_complete_json(accumulated)
            if complete is not None:
                return complete
            last_error = ProviderTimeoutError("provider_timeout_error:read_timeout")
            if attempt >= attempts:
                raise last_error from exc
        if attempt < attempts and delay_seconds > 0:
            time.sleep(delay_seconds)
            delay_seconds *= max(1.0, retry_policy.backoff_multiplier)
    if last_error is not None:
        raise last_error
    raise ProviderRuntimeError("provider_unknown_error")


def _set_response_read_timeout(response: object, timeout_seconds: float) -> bool:
    """Set the socket deadline behind urllib's buffered HTTPResponse.

    CPython's wrapper chain is normally ``response.fp.raw._sock``.  Walk a
    small explicit set of known wrappers instead of depending on one private
    shape; test doubles without a socket return ``False`` and keep using their
    iterator protocol.
    """

    candidates = [response]
    fp = getattr(response, "fp", None)
    if fp is not None:
        candidates.append(fp)
        raw = getattr(fp, "raw", None)
        if raw is not None:
            candidates.append(raw)
            sock = getattr(raw, "_sock", None)
            if sock is not None:
                candidates.append(sock)
    for candidate in reversed(candidates):
        setter = getattr(candidate, "settimeout", None)
        if callable(setter):
            setter(max(0.1, float(timeout_seconds)))
            return True
    return False


def _incomplete_json_has_whitespace_padding(text: str, *, min_run: int = 64) -> bool:
    """True when a JSON value started but the model is now emitting padding.

    Representation-only transport stop: the bytes already received are
    unchanged and still fail closed if they are not a complete value.
    """

    if _first_complete_json(text) is not None:
        return False
    if "{" not in text and "[" not in text:
        return False
    padding = len(text) - len(text.rstrip(" \t\r\n"))
    return padding >= max(1, int(min_run))


def _first_complete_json(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None
    candidate = _balanced_json_candidate(text, start)
    if candidate is None:
        return None
    try:
        json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return candidate


def _balanced_json_candidate(text: str, start: int) -> str | None:
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
            if depth < 0:
                return None
    return None


def _auth_headers(provider: LLMProvider, config: LLMConfig) -> dict[str, str]:
    provider_value = getattr(provider, "value", str(provider))
    if provider_value in {"openai", "openrouter"}:
        return {"Authorization": f"Bearer {_api_key(provider, config)}"}
    if provider_value == "anthropic":
        return {"x-api-key": _api_key(provider, config)}
    return {}


#: Some OpenAI-compatible gateways sit behind Cloudflare-style edge protection
#: that rejects urllib's default ``Python-urllib/x.y`` user agent (HTTP 403,
#: Cloudflare error 1010).  A plain curl-style user agent is accepted while
#: keeping the request non-browser, and it is harmless for every local or
#: remote provider the client already talks to.
_CLIENT_USER_AGENT = "code2paper/1.0 (curl-like; +https://opencode.ai/zen/go)"


def _request_headers(provider: LLMProvider, config: LLMConfig) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "User-Agent": _CLIENT_USER_AGENT,
        **_auth_headers(provider, config),
    }


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


def _normalized_usage(value: object, prefix: str = "") -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    normalized: dict[str, int] = {}
    for key, item in value.items():
        label = str(key) if not prefix else f"{prefix}.{key}"
        if isinstance(item, bool):
            continue
        if isinstance(item, int):
            normalized[label] = item
            continue
        if isinstance(item, dict):
            nested = _normalized_usage(item, label)
            if nested:
                normalized.update(nested)
    if not prefix:
        thinking_chars = int(_STREAM_METRICS.get("thinking_chars") or 0)
        if thinking_chars and "thinking_chars" not in normalized:
            normalized["thinking_chars"] = thinking_chars
            normalized.setdefault("thinking_tokens_est", max(1, thinking_chars // 4))
    return normalized or None


def _schema_name(request: LLMRequest) -> str:
    name = request.schema_name or "structured_response"
    return "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in name)


def _strip_unique_items(schema: object) -> object:
    """Recursively remove ``uniqueItems`` keys from a JSON schema.

    xgrammar (used by loopback vLLM) rejects ``uniqueItems``.  The keyword is a
    grammar hint only; downstream binding/authorship gates enforce uniqueness,
    so removing it does not weaken the contract.  ``enum``/``const``/``minLength``
    and other supported constraints are preserved so guided decoding still
    prevents representation errors.
    """

    if isinstance(schema, dict):
        return {
            key: _strip_unique_items(value)
            for key, value in schema.items()
            if key != "uniqueItems"
        }
    if isinstance(schema, list):
        return [_strip_unique_items(item) for item in schema]
    return schema


def _json_dumps(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _retry_policy(config: LLMConfig) -> RetryPolicy:
    return RetryPolicy(
        max_attempts=max(1, config.retry_max_attempts),
        initial_delay_seconds=max(0.0, config.retry_initial_delay_seconds),
        backoff_multiplier=max(1.0, config.retry_backoff_multiplier),
    )


def _cache_key(
    config: LLMConfig,
    request: LLMRequest,
    capability_profile: LLMCapabilityProfile,
) -> str:
    return hash_text(
        json.dumps(
            {
                "provider": config.provider.value,
                "model": config.model,
                "temperature": config.temperature,
                "max_output_tokens": config.max_output_tokens,
                "reasoning_effort": config.reasoning_effort,
                "thinking_token_budget": config.thinking_token_budget,
                "top_p": config.top_p,
                "top_k": config.top_k,
                "seed": config.seed,
                "max_input_tokens": config.max_input_tokens,
                "role": config.role,
                "prompt_template_version": config.prompt_template_version,
                "capability_profile": capability_profile.model_dump(mode="json"),
                "request_input_hash": request.input_hash,
            },
            sort_keys=True,
        )
    ).replace("sha256:", "")


def _cache_dir() -> Path:
    root = os.environ.get("CODE2PAPER_LLM_CACHE_DIR", "/tmp/code2paper_llm_cache")
    return Path(root)


def _read_cache(
    config: LLMConfig,
    request: LLMRequest,
    capability_profile: LLMCapabilityProfile,
) -> _ProviderResult | None:
    path = _cache_dir() / f"{_cache_key(config, request, capability_profile)}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    text = payload.get("text")
    if not isinstance(text, str):
        return None
    return _ProviderResult(
        text=text,
        response_mode=str(payload.get("response_mode") or ""),
        finish_reason=str(payload.get("finish_reason") or ""),
        token_usage=_normalized_usage(payload.get("token_usage")),
    )


def _write_cache(
    config: LLMConfig,
    request: LLMRequest,
    capability_profile: LLMCapabilityProfile,
    result: _ProviderResult,
) -> None:
    path = _cache_dir() / f"{_cache_key(config, request, capability_profile)}.json"
    temporary = ""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(_json_dumps({
                "cache_schema_version": "2.0",
                "provider": config.provider.value,
                "model": config.model,
                "reasoning_effort": config.reasoning_effort,
                "thinking_token_budget": config.thinking_token_budget,
                "prompt_template_version": config.prompt_template_version,
                "capability_profile": capability_profile.model_dump(mode="json"),
                "request_input_hash": request.input_hash,
                "text": result.text,
                "response_mode": result.response_mode,
                "finish_reason": result.finish_reason,
                "token_usage": result.token_usage or {},
            }))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError:
        if temporary:
            try:
                os.unlink(temporary)
            except OSError:
                pass
        return
