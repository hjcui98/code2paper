"""LLM integration primitives for code2paper.

The current package keeps provider calls explicit. Full authoring stages can
depend on these helpers without forcing API SDK dependencies into the scaffold.
"""

from code2paper.llm.client import LLMClient, LLMRequest, LLMResponse
from code2paper.llm.providers import load_llm_config_from_env

__all__ = [
    "LLMClient",
    "LLMRequest",
    "LLMResponse",
    "load_llm_config_from_env",
]

