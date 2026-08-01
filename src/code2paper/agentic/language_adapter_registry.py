"""Execution-time registry for language behavior adapters."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from code2paper.agentic.behavior_graph import LanguageBehaviorAdapter
from code2paper.agentic.javascript_behavior_adapter import JavaScriptBehaviorAdapter
from code2paper.agentic.python_behavior_adapter import PythonBehaviorAdapter


class LanguageAdapterRegistry:
    """Small explicit registry; evidence policy remains outside the adapter."""

    def __init__(self, adapters: Mapping[str, LanguageBehaviorAdapter] | None = None) -> None:
        self._adapters: dict[str, LanguageBehaviorAdapter] = dict(adapters or {})

    def register(self, adapter: LanguageBehaviorAdapter, *, replace: bool = False) -> None:
        language = str(adapter.language).strip().lower()
        if not language:
            raise ValueError("language adapter must declare a language")
        if language in self._adapters and not replace:
            raise ValueError(f"language adapter already registered: {language}")
        self._adapters[language] = adapter

    def get(self, language: str) -> LanguageBehaviorAdapter:
        key = str(language).strip().lower()
        try:
            return self._adapters[key]
        except KeyError as exc:
            raise KeyError(f"no language adapter registered for {key!r}") from exc

    def supported_languages(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))

    def for_files(self, files: Mapping[str, Any], *, default: str = "python") -> LanguageBehaviorAdapter:
        suffixes = {str(path).lower().rsplit(".", 1)[-1] for path in files if "." in str(path)}
        if suffixes.intersection({"js", "jsx", "ts", "tsx"}) and not suffixes.intersection({"py"}):
            return self.get("javascript")
        return self.get(default)


def default_language_adapter_registry() -> LanguageAdapterRegistry:
    registry = LanguageAdapterRegistry()
    registry.register(PythonBehaviorAdapter())
    registry.register(JavaScriptBehaviorAdapter())
    return registry


__all__ = ["LanguageAdapterRegistry", "default_language_adapter_registry"]
