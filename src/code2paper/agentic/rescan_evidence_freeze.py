from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from code2paper.agentic.retrieval import RetrievalRescanPlan, SymbolIndexEntry, SymbolIndexReport
from code2paper.core.schemas import RawEvidencePack, SourceType


@dataclass(frozen=True, slots=True)
class RescanEvidenceFreezeResult:
    raw_pack: RawEvidencePack
    snippets_payload: dict[str, Any]
    evidence_index: dict[str, str]
    frozen_count: int


def freeze_rescan_symbol_index_evidence(
    *,
    project_root: str | Path,
    raw_pack: RawEvidencePack,
    snippets_payload: dict[str, Any],
    evidence_index: dict[str, str],
    rescan_plan: RetrievalRescanPlan,
    symbol_index: SymbolIndexReport,
) -> RescanEvidenceFreezeResult:
    root = Path(project_root).expanduser().resolve()
    entries = _matched_symbol_entries(rescan_plan=rescan_plan, symbol_index=symbol_index)
    existing_keys = {_evidence_location_key(item.path, item.symbol or "", item.line_start, item.line_end) for item in raw_pack.evidence_items}
    next_id = _next_evidence_number(raw_pack)
    evidence_items = list(raw_pack.evidence_items)
    snippets = _payload_snippets(snippets_payload)
    updated_index = dict(evidence_index)
    frozen_count = 0
    for entry in entries:
        key = _evidence_location_key(entry.path, entry.symbol, entry.start_line, entry.end_line)
        if key in existing_keys:
            continue
        excerpt = _entry_excerpt(root=root, entry=entry)
        if not excerpt.strip():
            continue
        evidence_id = f"E{next_id}"
        next_id += 1
        snippet_id = f"AGENTIC_RESCAN_{evidence_id}"
        summary = _entry_summary(entry)
        source_type = _source_type(entry.path)
        # The repository still exposes a compatibility schema module alongside
        # core.schemas.  Add plain values and revalidate through the incoming
        # pack class so enum instances never leak across that boundary.
        evidence_items.append(
            {
                "evidence_id": evidence_id,
                "source_type": source_type.value,
                "path": entry.path,
                "symbol": entry.symbol or None,
                "line_start": entry.start_line,
                "line_end": entry.end_line,
                "config_key": entry.symbol if source_type == SourceType.CONFIG else None,
                "content_summary": summary,
                "tags": ["agentic_rescan", "symbol_index", f"snippet_id:{snippet_id}"],
                "confidence": 0.82,
                "excerpt_hash": _excerpt_hash(entry=entry, excerpt=excerpt),
            }
        )
        snippets.append(
            {
                "snippet_id": snippet_id,
                "source": {
                    "path": entry.path,
                    "symbol": entry.symbol,
                    "start_line": entry.start_line,
                    "end_line": entry.end_line,
                },
                "text": excerpt,
                "summary": summary,
                "role": "agentic_rescan_symbol_index",
                "confidence": 0.82,
            }
        )
        updated_index[snippet_id] = evidence_id
        existing_keys.add(key)
        frozen_count += 1
    raw_pack_payload = raw_pack.model_dump(mode="python")
    raw_pack_payload["evidence_items"] = evidence_items
    normalized_raw_pack = raw_pack.__class__.model_validate(raw_pack_payload)
    return RescanEvidenceFreezeResult(
        raw_pack=normalized_raw_pack,
        snippets_payload={**snippets_payload, "snippets": snippets},
        evidence_index=updated_index,
        frozen_count=frozen_count,
    )


def _matched_symbol_entries(
    *,
    rescan_plan: RetrievalRescanPlan,
    symbol_index: SymbolIndexReport,
) -> list[SymbolIndexEntry]:
    result: list[SymbolIndexEntry] = []
    seen: set[tuple[str, str, int, int]] = set()
    for item in rescan_plan.items:
        if not item.path:
            continue
        for entry in symbol_index.candidates:
            if not _same_path(entry.path, item.path):
                continue
            if item.symbol and entry.symbol != item.symbol:
                continue
            key = (entry.path, entry.symbol, entry.start_line, entry.end_line)
            if key in seen:
                continue
            seen.add(key)
            result.append(entry)
    return result


def _payload_snippets(snippets_payload: dict[str, Any]) -> list[dict[str, Any]]:
    snippets = snippets_payload.get("snippets")
    if not isinstance(snippets, list):
        return []
    return [dict(snippet) for snippet in snippets if isinstance(snippet, dict)]


def _same_path(path: str, hint: str) -> bool:
    normalized_path = path.replace("\\", "/").strip("/")
    normalized_hint = hint.replace("\\", "/").strip("/")
    return normalized_path == normalized_hint or normalized_path.endswith(f"/{normalized_hint}")


def _source_type(path: str) -> SourceType:
    lowered = path.lower()
    if lowered.endswith(".sh"):
        return SourceType.BASH
    if lowered.endswith((".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", "makefile")):
        return SourceType.CONFIG
    return SourceType.SOURCE


def _entry_excerpt(*, root: Path, entry: SymbolIndexEntry) -> str:
    path = root / entry.path
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return ""
    start = max(entry.start_line, 1)
    end = max(entry.end_line, start)
    return "\n".join(lines[start - 1 : end])


def _entry_summary(entry: SymbolIndexEntry) -> str:
    label = entry.symbol or entry.path
    return f"Agentic rescan froze symbol-index location {label} in {entry.path}."


def _excerpt_hash(*, entry: SymbolIndexEntry, excerpt: str) -> str:
    payload = "\n".join([entry.path, entry.symbol, str(entry.start_line), str(entry.end_line), excerpt])
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _evidence_location_key(path: str, symbol: str, line_start: int | None, line_end: int | None) -> tuple[str, str, int, int]:
    return (path.replace("\\", "/"), symbol, line_start or 0, line_end or 0)


def _next_evidence_number(raw_pack: RawEvidencePack) -> int:
    numbers: list[int] = []
    for item in raw_pack.evidence_items:
        suffix = item.evidence_id.removeprefix("E")
        if suffix.isdigit():
            numbers.append(int(suffix))
    return max(numbers, default=0) + 1
