"""Pipeline stage 1: story-first code intake with embedded CodeIntakeAgent."""

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
from code2paper.author_questionnaire import load_author_markers
from code2paper.export.run_manifest import hash_file
from code2paper.schemas import (
    ArtifactHash,
    CommentIndex,
    LLMConfig,
    LLMProvider,
    Phase1Manifest,
    RawContextIndex,
    RawEvidencePack,
    ContextMap,
)
from code2paper.story_first import to_method_summary, to_structured_sections


def run_stage1_code_intake(
    *,
    project_root: Path,
    method_root: Path,
    author_markers_path: str,
    llm_config: LLMConfig,
    project_id: str | None = None,
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
    state["method_experiment_structured_summary"] = to_method_summary(author_markers)
    state["structured_sections"] = to_structured_sections(author_markers)
    state["paper_objects"] = {}
    state["enable_code_intake_llm_review"] = llm_config.provider != LLMProvider.NONE
    state["config"] = {
        "code_intake": {
            "snippet_budget": {
                "max_total_snippet_lines": 4000,
                "max_single_snippet_lines": 300,
                "top_k_per_role": 12,
            },
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
        "raw_evidence_pack": method_root / "raw_evidence_pack.json",
        "code_sources": method_root / "code_sources.json",
        "core_snippets": method_root / "core_snippets.json",
        "code_intake_report": method_root / "code_intake_report.json",
        "method_code_alignment": method_root / "method_code_alignment.json",
        "author_marker_method_summary": method_root / "author_marker_method_summary.json",
        "snippet_evidence_map": method_root / "snippet_evidence_map.json",
        "phase1_manifest": method_root / "phase1_manifest.json",
    }
    _write_json(paths["raw_evidence_pack"], raw_pack.model_dump(mode="json"))
    _write_json(paths["code_sources"], code_sources)
    _write_json(paths["core_snippets"], core_snippets)
    _write_json(paths["code_intake_report"], code_intake_report)
    _write_json(paths["method_code_alignment"], method_code_alignment)
    _write_json(paths["author_marker_method_summary"], state["method_experiment_structured_summary"])
    _write_json(paths["snippet_evidence_map"], snippet_to_evidence)

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


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

