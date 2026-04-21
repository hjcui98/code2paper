"""Tiny template helper for embedded agent prompts."""

from __future__ import annotations

import re
from typing import Any


class Template:
    """Minimal subset of Jinja2's Template used by the copied prompts."""

    def __init__(self, text: str) -> None:
        self.text = text

    def render(self, **kwargs: Any) -> str:
        def replace(match: re.Match[str]) -> str:
            key = match.group(1).strip()
            return str(kwargs.get(key, ""))

        return re.sub(r"{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}", replace, self.text)

