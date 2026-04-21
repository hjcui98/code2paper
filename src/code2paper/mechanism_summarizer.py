"""Mechanism summary facade."""

from __future__ import annotations

from .method_evidence import _mechanism_description


def summarize_mechanism(stage_name: str) -> str:
    return _mechanism_description(stage_name)

