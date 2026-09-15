"""Model-owned tokenizer adapters used by the unified request budget.

The unified budget must measure the same chat sequence that the OpenAI
compatible client sends. VllmOpenAIChatTokenizer delegates that exact
chat-template application to vLLM's read-only /tokenize endpoint; it does
not generate text and it never handles credentials beyond the local loopback
endpoint already configured for the run.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


class TokenizerUnavailableError(RuntimeError):
    """The declared model tokenizer could not measure a request."""


def _json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _tokenize_endpoint(base_url: str) -> str:
    raw = str(base_url or "").strip().rstrip("/")
    if not raw:
        raise TokenizerUnavailableError("tokenizer endpoint is empty")
    parsed = urlsplit(raw)
    if not parsed.scheme or not parsed.netloc:
        raise TokenizerUnavailableError("tokenizer endpoint is not an absolute URL")
    path = parsed.path.rstrip("/")
    if path.endswith("/v1"):
        path = path[:-3]
    return urlunsplit((parsed.scheme, parsed.netloc, f"{path}/tokenize", "", ""))


def _strip_unique_items(value: object) -> object:
    """Mirror the loopback schema normalization performed by ``LLMClient``."""

    if isinstance(value, dict):
        return {
            str(key): _strip_unique_items(item)
            for key, item in value.items()
            if key != "uniqueItems"
        }
    if isinstance(value, list):
        return [_strip_unique_items(item) for item in value]
    return value


@dataclass(frozen=True)
class VllmOpenAIChatTokenizer:
    """Read-only vLLM tokenizer for the current OpenAI-compatible model.

    identity is persisted in the meter and must be the same for prepare, send,
    and resume. The endpoint returns the count after applying the model's chat
    template to messages; component counts remain available through encode for
    the separate schema/scaffolding diagnostics.
    """

    base_url: str
    model: str
    timeout_seconds: int = 30
    identity: str = ""

    def __post_init__(self) -> None:
        if not str(self.model or "").strip():
            raise ValueError("model tokenizer requires a model identity")
        object.__setattr__(self, "base_url", str(self.base_url).strip().rstrip("/"))
        object.__setattr__(
            self,
            "identity",
            str(self.identity or "").strip()
            or f"vllm-openai-chat-template-v1:{self.model}@{self.base_url}",
        )

    @property
    def endpoint(self) -> str:
        return _tokenize_endpoint(self.base_url)

    def _post(self, payload: dict[str, object]) -> list[int]:
        request = Request(
            self.endpoint,
            data=_json_dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "code2paper-token-meter/1",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=max(1, int(self.timeout_seconds))) as response:
                body = response.read().decode("utf-8")
        except (HTTPError, URLError, OSError, TimeoutError) as exc:
            raise TokenizerUnavailableError(
                f"tokenizer request failed:{type(exc).__name__}"
            ) from exc
        try:
            value = json.loads(body)
        except json.JSONDecodeError as exc:
            raise TokenizerUnavailableError("tokenizer response is not JSON") from exc
        if not isinstance(value, dict) or not isinstance(value.get("tokens"), list):
            raise TokenizerUnavailableError("tokenizer response has no token list")
        try:
            tokens = [int(item) for item in value["tokens"]]
        except (TypeError, ValueError) as exc:
            raise TokenizerUnavailableError("tokenizer response has invalid tokens") from exc
        if any(item < 0 for item in tokens):
            raise TokenizerUnavailableError("tokenizer response has negative token id")
        return tokens

    def encode(self, text: str) -> list[int]:
        """Count a standalone text component with the same model tokenizer."""

        return self._post({"model": self.model, "prompt": str(text)})

    def encode_response_schema(self, schema: object) -> list[int]:
        """Count the schema serialization that the loopback client sends."""

        host = (urlsplit(self.base_url).hostname or "").lower()
        value = _strip_unique_items(schema) if host in {
            "127.0.0.1", "localhost", "::1"
        } else schema
        return self.encode(_json_dumps(value))

    def encode_wire_request(
        self,
        *,
        prompt: str,
        input_payload: object,
        response_schema: object,
        response_mode: str = "native_json_schema",
        enable_thinking: bool | None = None,
    ) -> list[int]:
        """Count the exact OpenAI-compatible chat messages sent by the client.

        Native JSON schema is carried in response_format and therefore is
        accounted separately by the unified budget. Prompt-only and JSON
        object modes append the same schema instruction that the client puts in
        the system message.
        """

        system_content = str(prompt)
        if response_schema and response_mode == "json_object":
            system_content += "\nReturn JSON matching this schema:\n" + _json_dumps(
                response_schema
            )
        elif response_schema and response_mode not in {
            "native_json_schema",
            "json_object",
        }:
            system_content += "\nReturn only JSON matching this schema:\n" + _json_dumps(
                response_schema
            )
        payload: dict[str, object] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": _json_dumps(input_payload)},
            ],
        }
        if enable_thinking is not None:
            payload["chat_template_kwargs"] = {
                "enable_thinking": bool(enable_thinking)
            }
        return self._post(payload)


def prepare_vllm_openai_chat_tokenizer(
    *,
    llm_config: object,
    out_root: str | os.PathLike[str],
    require_loopback_8006: bool = True,
) -> VllmOpenAIChatTokenizer:
    """Admit and persist the tokenizer for the configured OpenAI-compatible run.

    The normal Method Agent and the authoring replay must measure the same
    model-owned chat template.  Keeping the runtime preflight here prevents
    either entry point from silently selecting a different endpoint or a
    historical byte proxy.  The function performs only health/model/tokenize
    checks and writes non-secret identity metadata to the run root.
    """

    provider = str(
        getattr(getattr(llm_config, "provider", None), "value", getattr(llm_config, "provider", ""))
        or ""
    ).strip().casefold()
    if provider != "openai":
        raise ValueError("unified_live_tokenizer_requires_openai_compatible_provider")

    base_url = str(
        os.environ.get("CODE2PAPER_OPENAI_BASE_URL", "") or ""
    ).strip().rstrip("/")
    if not base_url:
        # ``openai_compatible_base_url`` is intentionally not imported here:
        # it returns a chat/completions URL, while this adapter owns the /v1
        # origin used by both /health and /tokenize.
        raise ValueError("unified_live_tokenizer_base_url_missing")
    parsed = urlsplit(base_url)
    allowed_hosts = {"127.0.0.1", "localhost", "::1"}
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or (require_loopback_8006 and parsed.hostname not in allowed_hosts)
        or (require_loopback_8006 and int(parsed.port or 0) != 8006)
        or parsed.path.rstrip("/") != "/v1"
    ):
        raise ValueError("unified_live_tokenizer_requires_8006_loopback_v1")

    origin = base_url[:-3]
    headers = {"User-Agent": "code2paper-unified-token-meter/1"}

    def _get_json(path: str) -> tuple[int, object]:
        request = Request(origin + path, headers=headers, method="GET")
        try:
            with urlopen(request, timeout=20) as response:
                raw = response.read().decode("utf-8")
                status = int(response.status)
        except (HTTPError, URLError, OSError, TimeoutError) as exc:
            raise ValueError(
                f"unified_runtime_preflight_failed:{type(exc).__name__}"
            ) from exc
        if path == "/health" and not raw.strip():
            # vLLM commonly returns an empty successful health body.
            return status, {}
        try:
            return status, json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"unified_runtime_preflight_invalid_json:{path}") from exc

    health_status, _health = _get_json("/health")
    if health_status != 200:
        raise ValueError(f"unified_runtime_health_failed:{health_status}")
    models_status, models_payload = _get_json("/v1/models")
    model_rows = (
        models_payload.get("data", [])
        if isinstance(models_payload, dict)
        else []
    )
    served_models = tuple(sorted(
        str(row.get("id") or "")
        for row in model_rows
        if isinstance(row, dict) and str(row.get("id") or "").strip()
    ))
    model = str(getattr(llm_config, "model", "") or "").strip()
    if models_status != 200 or model not in served_models:
        raise ValueError(
            "unified_runtime_model_identity_failed:" + ",".join(served_models)
        )
    runtime_identity = {
        "provider": provider,
        "base_url": base_url,
        "configured_model": model,
        "served_model_ids": list(served_models),
    }
    runtime_bytes = json.dumps(
        runtime_identity,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    runtime_digest = "sha256:" + hashlib.sha256(runtime_bytes).hexdigest()
    identity = (
        f"vllm-openai-chat-template-v1:{model}|{base_url}|{runtime_digest}"
    )
    tokenizer = VllmOpenAIChatTokenizer(
        base_url=base_url,
        model=model,
        identity=identity,
    )
    try:
        probe_tokens = tokenizer.encode_wire_request(
            prompt="Return one JSON object.",
            input_payload={},
            response_schema={},
            response_mode="native_json_schema",
        )
    except Exception as exc:  # noqa: BLE001 - tokenizer admission is fail-closed
        raise ValueError(
            f"unified_tokenizer_preflight_failed:{type(exc).__name__}"
        ) from exc
    if not probe_tokens:
        raise ValueError("unified_tokenizer_preflight_empty")

    contract = {
        "schema_version": "1.0",
        "measurement_basis": "openai_chat_template_v1",
        "tokenizer_identity": tokenizer.identity,
        "runtime_identity": runtime_identity,
        "probe_token_count": len(probe_tokens),
        "status": "pass",
    }
    contract_path = (
        Path(out_root)
        / "artifacts"
        / "06_authoring"
        / "unified_tokenizer_contract_v1.json"
    )
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return tokenizer


__all__ = [
    "TokenizerUnavailableError",
    "VllmOpenAIChatTokenizer",
    "prepare_vllm_openai_chat_tokenizer",
]
