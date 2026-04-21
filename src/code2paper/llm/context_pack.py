"""Context pack helpers for LLM-bound prompts."""

from __future__ import annotations

from code2paper.export.run_manifest import hash_json_payload


def build_context_pack(*, name: str, artifacts: dict[str, object], token_budget: int | None = None) -> dict:
    pack = {
        "name": name,
        "artifacts": artifacts,
        "token_budget": token_budget,
    }
    pack["context_hash"] = hash_json_payload(pack)
    return pack

