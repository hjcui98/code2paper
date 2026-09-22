"""运行期有效配置的唯一 owner（审计 §A.1.6 / §A.2）。

两个要求：

1. **未知 narrative mode 不得静默回退 V3。** 计划选择只有一个 owner
   （`normalize_narrative_plan_mode`），入口身份冻结与实际 builder 都消费同一结果，
   而不是各自 `or "v3"`。
2. **实际生效的配置进入身份。** narrative mode、authoring context mode、输出协议、
   prompt/schema/tokenizer 与验收规则身份一起冻结进执行身份，否则"同一个输入"在
   不同模式/协议下会共享身份，复用与对照都会表达错的东西。
"""

from __future__ import annotations

import os
from typing import Any, Mapping

from code2paper.agentic.mechanism_context_models import canonical_json_bytes, sha256_digest

__all__ = [
    "NARRATIVE_PLAN_MODES",
    "UNKNOWN_NARRATIVE_PLAN_MODE",
    "UnknownNarrativePlanMode",
    "normalize_narrative_plan_mode",
    "capture_effective_config_digest",
    "EFFECTIVE_CONFIG_ENV_KEYS",
]

NARRATIVE_PLAN_MODES: tuple[str, ...] = ("v3", "v4", "shadow")

UNKNOWN_NARRATIVE_PLAN_MODE = "unknown_narrative_plan_mode"

#: 进入"有效配置身份"的环境变量：只有真正改变执行语义的协议/模式键。
EFFECTIVE_CONFIG_ENV_KEYS: tuple[str, ...] = (
    "CODE2PAPER_AUTHORING_CONTEXT_MODE",
    "CODE2PAPER_LLM_PUBLICATION_WRITER_RESPONSE_MODE",
    "CODE2PAPER_LLM_PUBLICATION_EDITOR_RESPONSE_MODE",
    "CODE2PAPER_LLM_STREAM_STRUCTURED",
)


class UnknownNarrativePlanMode(ValueError):
    """未知的 narrative plan mode：必须显式拒绝，不得回退到 V3（不变量 I2）。"""


def normalize_narrative_plan_mode(
    value: Any, *, source: str = "CODE2PAPER_INTENT_NARRATIVE_PLAN"
) -> str:
    """把配置值规范成受支持的 mode；未知值抛错而不是静默回退。"""

    candidate = str(value if value is not None else "").strip().casefold()
    if not candidate:
        return "v3"
    if candidate not in NARRATIVE_PLAN_MODES:
        raise UnknownNarrativePlanMode(
            f"{UNKNOWN_NARRATIVE_PLAN_MODE}:{candidate}:{source}"
        )
    return candidate


def _env_value(name: str, environment: Mapping[str, str] | None = None) -> str:
    source: Mapping[str, str] = environment if environment is not None else os.environ
    return str(source.get(name, "") or "").strip()


def capture_effective_config_digest(
    *,
    llm_config: Any | None = None,
    narrative_plan_mode: Any | None = None,
    authoring_context_mode: Any | None = None,
    response_protocol: Any | None = None,
    tokenizer_identity: str | None = None,
    validator_bundle_digest: str | None = None,
    environment: Mapping[str, str] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """返回有效配置的有效载荷与 digest（``{"payload": ..., "digest": ...}``）。

    未知 narrative mode 在这里就会被拒绝：身份构造是"任何模型调用之前"的关口。
    """

    mode = normalize_narrative_plan_mode(
        narrative_plan_mode
        if narrative_plan_mode is not None
        else _env_value("CODE2PAPER_INTENT_NARRATIVE_PLAN", environment)
    )
    context_mode = str(
        authoring_context_mode
        if authoring_context_mode is not None
        else _env_value("CODE2PAPER_AUTHORING_CONTEXT_MODE", environment)
        or "legacy"
    ).strip().casefold() or "legacy"
    protocol = {
        "explicit": response_protocol if response_protocol is not None else None,
        "environment": {
            key: _env_value(key, environment) for key in EFFECTIVE_CONFIG_ENV_KEYS
        },
    }
    # §C.2：段数上限策略（值/来源/是否显式实验）属于有效配置的一部分，必须随身份冻结，
    # 不能让环境变量在不改变身份的情况下改契约。
    from code2paper.agentic.unified_context_compiler import (
        semantic_paragraph_limit_policy,
    )

    paragraph_limit = semantic_paragraph_limit_policy(environment)
    payload: dict[str, Any] = {
        "narrative_plan_mode": mode,
        "semantic_paragraph_limit": paragraph_limit,
        "authoring_context_mode": context_mode,
        "response_protocol": protocol,
        "prompt_bundle": {
            "role": str(getattr(llm_config, "role", "") or ""),
            "prompt_template_version": str(
                getattr(llm_config, "prompt_template_version", "") or ""
            ),
        },
        "tokenizer": str(tokenizer_identity or "").strip() or "unspecified",
        "validator_bundle": str(validator_bundle_digest or "").strip() or "unspecified",
    }
    if extra:
        payload["extra"] = dict(extra)
    return {"payload": payload, "digest": sha256_digest(canonical_json_bytes(payload))}
