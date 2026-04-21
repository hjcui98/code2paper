"""User-guided focus term extraction and relevance scoring helpers."""

from __future__ import annotations

import os
import re

FOCUS_ENV_KEYS = ("CODE2PAPER_USER_FOCUS", "CODE2PAPER_FOCUS_QUERY")
_TOKEN_PATTERN = re.compile(r"[a-z0-9_./+-]{2,}")
_SPLIT_PATTERN = re.compile(r"[\n,;|]+")

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "our",
    "please",
    "that",
    "the",
    "this",
    "to",
    "we",
    "with",
}

_BOILERPLATE_MARKERS = (
    "licensed under",
    "apache license",
    "copyright",
    "all rights reserved",
    "you may obtain a copy",
    "usage:",
    "from .",
    "import ",
    "http://www.apache.org/licenses",
    "without warranties or conditions",
)


def load_focus_terms(explicit_focus: str | None = None) -> list[str]:
    raw = explicit_focus if explicit_focus is not None else _first_focus_env_value()
    if not raw:
        return []
    return _tokenize_focus(raw)


def relevance_score(*fragments: str, focus_terms: list[str] | None = None) -> int:
    terms = focus_terms or load_focus_terms()
    if not terms:
        return 0
    text = " ".join(fragment for fragment in fragments if fragment).lower()
    if not text:
        return 0
    score = 0
    for term in terms:
        if term not in text:
            continue
        if f"/{term}" in text or f"::{term}" in text:
            score += 3
        else:
            score += 1
    return score


def is_boilerplate_text(text: str) -> bool:
    lowered = (text or "").lower()
    if not lowered:
        return False
    return any(marker in lowered for marker in _BOILERPLATE_MARKERS)


def _first_focus_env_value() -> str:
    for key in FOCUS_ENV_KEYS:
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return ""


def _tokenize_focus(text: str) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for chunk in _SPLIT_PATTERN.split(text.lower()):
        for token in _TOKEN_PATTERN.findall(chunk):
            if token in _STOPWORDS:
                continue
            if token in seen:
                continue
            seen.add(token)
            terms.append(token)
            if len(terms) >= 64:
                return terms
    return terms
