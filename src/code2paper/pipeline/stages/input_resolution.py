"""Stage 1 Input Resolution: fuse rough intent and code marks into resolved markers."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import yaml

from code2paper.cli.prepare import run_prepare
from code2paper.core.input_resolution import ResolvedAuthorInput, resolve_author_input
from code2paper.core.output_names import method_output
from code2paper.core.schemas import LLMConfig
from code2paper.export.run_manifest import hash_file


def run_input_resolution(
    *,
    author_markers_path: str | Path | None,
    intent_path: str | Path | None,
    project_root: Path,
    out_root: Path,
    project_id: str | None,
    core_top_k: int,
    annotation_required: bool,
    llm_config: LLMConfig | None = None,
    skip_draft_bootstrap: bool = False,
) -> ResolvedAuthorInput:
    input_root = method_output(out_root, "input_manifest").parent
    input_root.mkdir(parents=True, exist_ok=True)
    raw_author = str(author_markers_path or "").strip()
    raw_intent = str(intent_path or "").strip()
    if raw_author:
        resolved_author_path = Path(raw_author).expanduser().resolve()
        if not resolved_author_path.is_file():
            raise FileNotFoundError(f"author markers file not found: {resolved_author_path}")
        resolved = ResolvedAuthorInput(
            source="author",
            effective_author_markers_path=resolved_author_path,
        )
    elif raw_intent:
        resolved_intent_path = Path(raw_intent).expanduser().resolve()
        result = run_prepare(
            project_root=project_root,
            draft_path=resolved_intent_path,
            out_root=out_root,
            project_id=project_id,
            core_top_k=core_top_k,
            llm_provider=_llm_provider_name(llm_config),
            llm_model=getattr(llm_config, "model", None),
            skip_draft_bootstrap=skip_draft_bootstrap,
        )
        resolved = ResolvedAuthorInput(
            source="draft",
            effective_author_markers_path=Path(result["final_markers"]),
            intent_path=resolved_intent_path,
            generated_author_markers_path=Path(result["coarse_markers"]),
        )
    else:
        resolved = resolve_author_input(
            intent_path=intent_path,
            project_root=project_root,
            method_root=input_root,
            core_top_k=core_top_k,
            annotation_required=annotation_required,
            llm_config=llm_config,
        )
    resolved_yaml = method_output(out_root, "resolved_author_markers_yaml")
    resolved_json = method_output(out_root, "resolved_author_markers_json")
    _write_resolved_markers(resolved.effective_author_markers_path, resolved_yaml, resolved_json)
    _copy_marker_if_present(
        resolved.generated_author_markers_path,
        method_output(out_root, "generated_author_markers_yaml"),
        method_output(out_root, "generated_author_markers_json"),
    )
    _copy_marker_if_present(
        resolved.effective_author_markers_path,
        method_output(out_root, "refined_markers_yaml"),
        method_output(out_root, "refined_markers_json"),
    )
    manifest = {
        "stage": "input_resolution",
        "mode": resolved.source,
        "project_root": str(project_root),
        "intent_path": str(resolved.intent_path or ""),
        "template_path": str(resolved.intent_path or ""),
        "effective_author_markers_path": str(resolved_yaml),
        "outputs": {
            name: _artifact(path)
            for name, path in {
                "generated_author_markers": resolved.generated_author_markers_path,
                "resolved_author_markers_yaml": resolved_yaml,
                "resolved_author_markers_json": resolved_json,
            }.items()
            if path
        },
        "blocked": False,
    }
    _write_json(method_output(out_root, "input_manifest"), manifest)
    return ResolvedAuthorInput(
        source=resolved.source,
        effective_author_markers_path=resolved_yaml,
        intent_path=resolved.intent_path,
        generated_author_markers_path=resolved.generated_author_markers_path,
    )


def _write_resolved_markers(source: Path, resolved_yaml: Path, resolved_json: Path) -> None:
    resolved_yaml.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, resolved_yaml)
    payload = yaml.safe_load(resolved_yaml.read_text(encoding="utf-8")) or {}
    _write_json(resolved_json, payload if isinstance(payload, dict) else {"value": payload})


def _copy_marker_if_present(source: Path | None, target_yaml: Path, target_json: Path) -> None:
    if source is None or not source.exists():
        return
    if source.resolve() != target_yaml.resolve():
        target_yaml.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target_yaml)
    else:
        target_yaml.parent.mkdir(parents=True, exist_ok=True)
    payload = yaml.safe_load(target_yaml.read_text(encoding="utf-8")) or {}
    _write_json(target_json, payload if isinstance(payload, dict) else {"value": payload})


def _llm_provider_name(llm_config: LLMConfig | None) -> str | None:
    if llm_config is None:
        return None
    provider = getattr(llm_config, "provider", None)
    value = getattr(provider, "value", provider)
    text = str(value or "").strip()
    return text or None


def _artifact(path: Path) -> dict[str, str]:
    return {"path": str(path), "hash": hash_file(path) if path.exists() else ""}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
