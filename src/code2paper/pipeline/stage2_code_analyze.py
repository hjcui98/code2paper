"""Pipeline stage 2: story-first code analysis with embedded CodeAnalyzerAgent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from code2paper.agents.bridge import (
    _build_code_method_analysis_payload,
    _build_raw_pack_from_snippets,
    _filter_postergen_outputs,
    _filter_raw_pack,
)
from code2paper.agents.code_analyzer import CodeAnalyzerAgent
from code2paper.agents.state.poster_state import create_state
from code2paper.alignment import align_code
from code2paper.author_questionnaire import load_author_markers
from code2paper.export.run_manifest import hash_file
from code2paper.schemas import (
    ArtifactHash,
    CodeAlignmentIR,
    CodeMethodAnalysis,
    LLMConfig,
    LLMProvider,
    Phase2Manifest,
    RawEvidencePack,
)
from code2paper.story_first import to_method_summary, to_structured_sections


def run_stage2_code_analyze(
    *,
    project_root: Path,
    method_root: Path,
    author_markers_path: str,
    llm_config: LLMConfig,
    project_id: str | None = None,
) -> tuple[CodeAlignmentIR, dict[str, Path]]:
    method_root.mkdir(parents=True, exist_ok=True)
    agent_root = method_root / "agent_workspace" / "code_analyzer"
    agent_root.mkdir(parents=True, exist_ok=True)

    author_markers = load_author_markers(author_markers_path)
    project_id_value = project_id or project_root.name.replace("-", "_")
    core_snippets = _read_json(method_root / "core_snippets.json")
    code_sources = _read_json(method_root / "code_sources.json")
    method_code_alignment = _read_json(method_root / "method_code_alignment.json")
    code_intake_report = _read_json(method_root / "code_intake_report.json")

    state = create_state(
        pdf_path=str(Path(author_markers_path).resolve()),
        text_model=llm_config.model or "gpt-4.1-mini",
        vision_model=llm_config.model or "gpt-4.1-mini",
        width=54,
        height=36,
        output_dir=str(agent_root),
        poster_name="code2paper_code_analyzer",
        text_provider=_state_provider(llm_config),
        vision_provider=_state_provider(llm_config),
    )
    state["repo_path"] = str(project_root)
    state["code_sources"] = code_sources
    state["core_snippets"] = core_snippets
    state["method_code_alignment"] = method_code_alignment
    state["code_intake_report"] = code_intake_report
    state["method_experiment_structured_summary"] = to_method_summary(author_markers)
    state["structured_sections"] = to_structured_sections(author_markers)
    state["paper_objects"] = {}
    state["dynamic_roles"] = _dynamic_roles(method_code_alignment)
    state["enable_code_analyzer_llm"] = llm_config.provider != LLMProvider.NONE

    state = CodeAnalyzerAgent()(state)
    _raise_agent_errors(state)

    code_facts = state.get("code_facts") or _read_json(agent_root / "content" / "code_facts.json")
    code_ir = state.get("code_ir") or _read_json(agent_root / "content" / "code_ir.json")
    entity_links = state.get("entity_links") or _read_json(agent_root / "content" / "entity_links.json")
    code_analysis_report = state.get("code_analysis_report") or _read_json(agent_root / "content" / "code_analysis_report.json")

    code_sources, core_snippets, code_facts, _removed = _filter_postergen_outputs(
        repo=project_root,
        author_markers=author_markers,
        code_sources=code_sources,
        core_snippets=core_snippets,
        code_facts=code_facts,
    )
    raw_pack, snippet_to_evidence = _build_raw_pack_from_snippets(
        repo=project_root,
        author_markers=author_markers,
        core_snippets=core_snippets,
        project_id=project_id_value,
    )
    raw_pack = _filter_raw_pack(raw_pack, repo=project_root, author_markers=author_markers)
    alignment = CodeAlignmentIR.model_validate(align_code(raw_pack, author_markers=author_markers).model_dump(mode="json"))
    analysis_payload = _build_code_method_analysis_payload(
        code_facts=code_facts,
        core_snippets=core_snippets,
        author_markers=author_markers,
        snippet_to_evidence=snippet_to_evidence,
        raw_pack=raw_pack,
    )
    analysis = CodeMethodAnalysis.model_validate(analysis_payload)

    paths = {
        "raw_evidence_pack": method_root / "raw_evidence_pack.json",
        "code_alignment_ir": method_root / "code_alignment_ir.json",
        "code_method_analysis": method_root / "code_method_analysis.json",
        "code_facts": method_root / "code_facts.json",
        "code_ir": method_root / "code_ir.json",
        "entity_links": method_root / "entity_links.json",
        "code_analysis_report": method_root / "code_analysis_report.json",
        "snippet_evidence_map": method_root / "snippet_evidence_map.json",
        "phase2_manifest": method_root / "phase2_manifest.json",
    }
    _write_json(paths["raw_evidence_pack"], raw_pack.model_dump(mode="json"))
    _write_json(paths["code_alignment_ir"], alignment.model_dump(mode="json"))
    _write_json(paths["code_method_analysis"], analysis.model_dump(mode="json"))
    _write_json(paths["code_facts"], code_facts)
    _write_json(paths["code_ir"], code_ir)
    _write_json(paths["entity_links"], entity_links)
    _write_json(paths["code_analysis_report"], code_analysis_report)
    _write_json(paths["snippet_evidence_map"], snippet_to_evidence)

    outputs = {
        name: ArtifactHash(path=str(path), hash=hash_file(path))
        for name, path in paths.items()
        if name != "phase2_manifest"
    }
    manifest = Phase2Manifest(
        project_id=project_id_value,
        llm_required=False,
        llm_available=llm_config.provider != LLMProvider.NONE,
        mode="story-first-code-analyzer",
        prompt_template_version=llm_config.prompt_template_version or "story-first-code-agents-v1",
        outputs=outputs,
        llm_call_logs=[],
        blocked_report="",
    )
    _write_json(paths["phase2_manifest"], manifest.model_dump(mode="json"))
    return alignment, paths


def _dynamic_roles(method_code_alignment: dict[str, Any]) -> list[str]:
    roles: list[str] = []
    for role in method_code_alignment.get("dynamic_roles", []) if isinstance(method_code_alignment, dict) else []:
        if isinstance(role, str) and role.strip():
            roles.append(role.strip())
    return roles


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

