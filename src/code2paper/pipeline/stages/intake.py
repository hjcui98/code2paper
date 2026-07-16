"""Phase 1 Intake: story-first code intake with embedded CodeIntakeAgent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from code2paper.agents.bridge import (
    _build_raw_pack_from_snippets,
    _filter_postergen_outputs,
    _filter_raw_pack,
)
from code2paper.agents.code_intake import CodeIntakeAgent
from code2paper.agents.state.poster_state import create_state
from code2paper.core.author_questionnaire import load_author_markers
from code2paper.export.run_manifest import hash_file
from code2paper.core.output_names import method_output
from code2paper.core.schemas import (
    ArtifactHash,
    CommentIndex,
    LLMConfig,
    LLMProvider,
    Phase1Manifest,
    RawContextIndex,
    RawEvidencePack,
    ContextMap,
)
from code2paper.core.story_first import to_method_summary, to_structured_sections


def run_phase1_intake(
    *,
    project_root: Path,
    method_root: Path,
    author_markers_path: str,
    llm_config: LLMConfig,
    project_id: str | None = None,
    retrieval_hints_overlay: dict[str, Any] | None = None,
) -> tuple[RawEvidencePack, CommentIndex, RawContextIndex, ContextMap, dict[str, Path]]:
    method_root.mkdir(parents=True, exist_ok=True)
    agent_root = method_root / "agent_workspace" / "code_intake"
    agent_root.mkdir(parents=True, exist_ok=True)

    author_markers = load_author_markers(author_markers_path)
    project_id_value = project_id or project_root.name.replace("-", "_")
    state = create_state(
        pdf_path=str(Path(author_markers_path).resolve()),
        text_model=llm_config.model or "gpt-4.1-mini",
        vision_model=llm_config.model or "gpt-4.1-mini",
        width=54,
        height=36,
        output_dir=str(agent_root),
        poster_name="code2paper_code_intake",
        text_provider=_state_provider(llm_config),
        vision_provider=_state_provider(llm_config),
    )
    state["repo_path"] = str(project_root)
    method_summary = to_method_summary(author_markers)
    if retrieval_hints_overlay:
        method_summary = _merge_retrieval_hints(method_summary, retrieval_hints_overlay)
    state["method_experiment_structured_summary"] = method_summary
    state["structured_sections"] = to_structured_sections(author_markers)
    state["paper_objects"] = {}
    state["enable_code_intake_llm_retrieval_planning"] = llm_config.provider != LLMProvider.NONE
    state["enable_code_intake_llm_review"] = llm_config.provider != LLMProvider.NONE
    state["config"] = {
        "code_intake": {
            "snippet_budget": {
                "max_total_snippet_lines": 4000,
                "max_single_snippet_lines": 300,
                "top_k_per_role": 12,
            },
            "llm_retrieval_planning": {"enabled": llm_config.provider != LLMProvider.NONE},
            "llm_review": {"max_iterations": 3},
            "method_alignment": {"min_coverage_score": 0.7, "auto_rescan": True},
        }
    }

    state = CodeIntakeAgent()(state)
    _raise_agent_errors(state)

    code_sources = state.get("code_sources") or _read_json(agent_root / "content" / "code_sources.json")
    core_snippets = state.get("core_snippets") or _read_json(agent_root / "content" / "core_snippets.json")
    code_intake_report = state.get("code_intake_report") or _read_json(agent_root / "content" / "code_intake_report.json")
    method_code_alignment = state.get("method_code_alignment") or _read_json(agent_root / "content" / "method_code_alignment.json")

    code_sources, core_snippets, _unused_code_facts, _removed = _filter_postergen_outputs(
        repo=project_root,
        author_markers=author_markers,
        code_sources=code_sources,
        core_snippets=core_snippets,
        code_facts={"modules": [], "pipeline_steps": []},
    )
    raw_pack, snippet_to_evidence = _build_raw_pack_from_snippets(
        repo=project_root,
        author_markers=author_markers,
        core_snippets=core_snippets,
        project_id=project_id_value,
    )
    raw_pack = _filter_raw_pack(raw_pack, repo=project_root, author_markers=author_markers)

    paths = {
        "evidence_raw": method_output(method_root, "evidence_raw"),
        "sources": method_output(method_root, "sources"),
        "snippets": method_output(method_root, "snippets"),
        "intake_report": method_output(method_root, "intake_report"),
        "intake_alignment": method_output(method_root, "intake_alignment"),
        "author_summary": method_output(method_root, "author_summary"),
        "evidence_index": method_output(method_root, "evidence_index"),
        "phase1_manifest": method_output(method_root, "phase1_manifest"),
    }
    _write_json(paths["evidence_raw"], raw_pack.model_dump(mode="json"))
    _write_json(paths["sources"], code_sources)
    _write_json(paths["snippets"], core_snippets)
    _write_json(paths["intake_report"], code_intake_report)
    _write_json(paths["intake_alignment"], method_code_alignment)
    _write_json(paths["author_summary"], state["method_experiment_structured_summary"])
    _write_json(paths["evidence_index"], snippet_to_evidence)

    manifest = Phase1Manifest(
        project_id=project_id_value,
        mode="story-first-code-intake",
        author_input_provided=True,
        outputs={
            name: ArtifactHash(path=str(path), hash=hash_file(path))
            for name, path in paths.items()
            if name != "phase1_manifest"
        },
    )
    _write_json(paths["phase1_manifest"], manifest.model_dump(mode="json"))
    empty_comment_index = CommentIndex()
    empty_context_index = RawContextIndex(project_id=project_id_value)
    empty_context_map = ContextMap()
    return raw_pack, empty_comment_index, empty_context_index, empty_context_map, paths


def _state_provider(llm_config: LLMConfig) -> str:
    return llm_config.provider.value if llm_config.provider != LLMProvider.NONE else "openai"


def _raise_agent_errors(state: dict[str, Any]) -> None:
    errors = [str(item) for item in state.get("errors", []) if str(item).strip()]
    if errors:
        raise RuntimeError("; ".join(errors[:8]))


def _merge_retrieval_hints(method_summary: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(method_summary)
    current_hints = method_summary.get("retrieval_hints") if isinstance(method_summary.get("retrieval_hints"), dict) else {}
    overlay_hints = overlay if isinstance(overlay, dict) else {}
    hints = dict(current_hints)
    for key in ("priority_paths", "claim_support_files", "negative_globs", "search_keywords"):
        hints[key] = _dedupe_strings(_as_string_list(hints.get(key)) + _as_string_list(overlay_hints.get(key)))
    hints["symbol_targets"] = _dedupe_symbol_targets(
        _as_symbol_targets(hints.get("symbol_targets")) + _as_symbol_targets(overlay_hints.get("symbol_targets"))
    )
    claim_targets = _dedupe_claim_targets(
        _as_claim_targets(hints.get("claim_targets")) + _as_claim_targets(overlay_hints.get("claim_targets"))
    )
    if claim_targets:
        hints["claim_targets"] = claim_targets
    merged["retrieval_hints"] = hints
    return merged


def _as_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _as_symbol_targets(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    targets: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        symbol = str(item.get("symbol") or "").strip()
        if path and symbol:
            targets.append({**item, "path": path, "symbol": symbol})
    return targets


def _as_claim_targets(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    targets: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        claim_id = str(item.get("claim_id") or "").strip()
        if claim_id:
            targets.append({**item, "claim_id": claim_id})
    return targets


def _dedupe_symbol_targets(targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for target in targets:
        key = (str(target.get("path") or ""), str(target.get("symbol") or ""))
        if not key[0] or not key[1] or key in seen:
            continue
        seen.add(key)
        result.append(target)
    return result


def _dedupe_claim_targets(targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for target in targets:
        claim_id = str(target.get("claim_id") or "").strip()
        if not claim_id or claim_id in seen:
            continue
        seen.add(claim_id)
        result.append(target)
    return result


def _dedupe_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
