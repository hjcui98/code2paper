from __future__ import annotations

import json
from pathlib import Path

from code2paper.agentic.contracts import AgentDecision, AgenticRunState, StageStatus, StageToolResult
from code2paper.agentic.legacy_retrieval_focus import evidence_repair_focus_payload
from code2paper.core.output_names import method_output
from code2paper.export.run_manifest import hash_file
from code2paper.llm.providers import load_llm_config_from_env
from code2paper.pipeline.stages.analysis import run_phase2_analysis
from code2paper.pipeline.stages.input_resolution import run_input_resolution


def run_input_resolution_stage(state: AgenticRunState) -> StageToolResult:
    resolved = run_input_resolution(
        author_markers_path=state.author_markers_path,
        intent_path=state.intent_path,
        project_root=state.project_root,
        out_root=state.out_root,
        project_id=state.project_id or None,
        core_top_k=state.core_top_k,
        annotation_required=False,
        llm_config=_llm_config(state),
        skip_draft_bootstrap=state.skip_draft_bootstrap,
    )
    artifacts = {
        "resolved_author_markers": str(resolved.effective_author_markers_path),
        "input_manifest": str(method_output(state.out_root, "input_manifest")),
    }
    if resolved.generated_author_markers_path:
        artifacts["generated_author_markers"] = str(resolved.generated_author_markers_path)
    return StageToolResult(
        stage="input_resolution",
        status=StageStatus.SUCCESS,
        artifacts=artifacts,
        summary=f"Resolved author input from {resolved.source}.",
    )


def run_analysis(state: AgenticRunState) -> StageToolResult:
    author_path = _require_author_markers(state)
    _alignment, paths = run_phase2_analysis(
        project_root=state.project_root,
        method_root=state.method_root,
        author_markers_path=author_path,
        project_id=state.project_id or None,
        llm_config=_llm_config(state),
        evidence_repair_focus=evidence_repair_focus_payload(state),
    )
    _refresh_phase1_manifest_hashes(state.method_root, paths, ("evidence_raw", "evidence_index"))
    result = _success("analysis", paths, "Analyzed implementation structure and code-method alignment.")
    if state.artifacts.get("evidence_repair_focus"):
        return result.model_copy(
            update={
                "artifacts": {**result.artifacts, "evidence_repair_focus": state.artifacts["evidence_repair_focus"]},
                "decisions": [
                    AgentDecision(
                        node="analysis_repair_focus",
                        decision="analysis_received_evidence_repair_focus",
                        rationale="Evidence sufficiency requested focused analysis repair and candidate task review.",
                        artifact_keys=[
                            "evidence_repair_focus",
                            *(["analysis_repair_tasks"] if "analysis_repair_tasks" in result.artifacts else []),
                        ],
                    )
                ],
            }
        )
    return result


def _llm_config(state: AgenticRunState):
    return load_llm_config_from_env(provider=state.llm_provider, model=state.llm_model)


def _require_author_markers(state: AgenticRunState) -> str:
    author_path = state.effective_author_markers_path
    if not author_path:
        raise ValueError("author_markers_path or resolved_author_markers artifact is required")
    return author_path


def _success(stage: str, paths: dict[str, Path], summary: str) -> StageToolResult:
    return StageToolResult(stage=stage, status=StageStatus.SUCCESS, artifacts=_existing_paths(paths), summary=summary)


def _existing_paths(paths: dict[str, Path]) -> dict[str, str]:
    return {name: str(path) for name, path in paths.items() if path.exists()}


def _refresh_phase1_manifest_hashes(method_root: Path, paths: dict[str, Path], names: tuple[str, ...]) -> None:
    manifest_path = method_output(method_root, "phase1_manifest")
    if not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        return
    outputs = manifest.get("outputs") if isinstance(manifest.get("outputs"), dict) else {}
    for name in names:
        path = paths.get(name)
        if path is not None and path.exists():
            outputs[name] = {"path": str(path), "hash": hash_file(path)}
    manifest["outputs"] = outputs
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
