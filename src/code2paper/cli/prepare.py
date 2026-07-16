from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from code2paper.draft_markers import (
    build_coarse_markers_payload,
    refine_markers_from_stage12,
    refine_markers_with_llm,
    load_yaml,
    run_code2flow_scan,
    suggest_mechanism_keywords,
    validate_author_markers_payload,
)
from code2paper.llm.providers import load_llm_config_from_env
from code2paper.core.output_names import method_output
from code2paper.core.output_paths import resolve_out_root, resolve_project_id
from code2paper.pipeline.stages.intake import run_phase1_intake
from code2paper.pipeline.stages.analysis import run_phase2_analysis
from code2paper.core.schemas import AuthorMarkers, LLMProvider


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="code2paper-prepare",
        description="Prepare refined author markers from a lightweight draft/template and code evidence.",
    )
    parser.add_argument("project_root", help="Target code repository")
    parser.add_argument("--draft", required=True, help="Coarse draft/template YAML path")
    parser.add_argument(
        "--out-root",
        default="",
        help="Output root for refined markers and bootstrap artifacts. Defaults to ./results/<repo_name>_<timestamp>/",
    )
    parser.add_argument("--project-id", default="")
    parser.add_argument("--core-top-k", type=int, default=12)
    parser.add_argument("--llm-provider", choices=[provider.value for provider in LLMProvider], default=None)
    parser.add_argument("--llm-model", default=None)
    parser.add_argument(
        "--skip-draft-bootstrap",
        action="store_true",
        help="Skip draft bootstrap Phase 1/2 intake+analysis when generating author markers.",
    )
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).expanduser().resolve()
    project_id = resolve_project_id(args.project_id, project_root=project_root, intent_path=args.draft)
    out_root = resolve_out_root(args.out_root, project_root=project_root, intent_path=args.draft)
    print(f"[code2paper-prepare] out_root={out_root}")
    result = run_prepare(
        project_root=project_root,
        draft_path=Path(args.draft).expanduser().resolve(),
        out_root=out_root,
        project_id=project_id,
        core_top_k=int(args.core_top_k),
        llm_provider=args.llm_provider,
        llm_model=args.llm_model,
        skip_draft_bootstrap=args.skip_draft_bootstrap,
    )
    print(json.dumps({key: str(value) if isinstance(value, Path) else value for key, value in result.items()}, ensure_ascii=False, indent=2))
    return int(result.get("exit_code", 0))


def run_prepare(
    *,
    project_root: Path,
    draft_path: Path,
    out_root: Path,
    project_id: str | None,
    core_top_k: int,
    code2flow_root: Path | None = None,
    llm_provider: str | None = None,
    llm_model: str | None = None,
    skip_draft_bootstrap: bool = False,
) -> dict[str, Any]:
    draft_payload = load_yaml(draft_path)
    draft_payload = _normalize_draft_payload_for_prepare(draft_payload)
    method_root = out_root / "paper" / "method"
    method_root.mkdir(parents=True, exist_ok=True)
    bootstrap_method_root = out_root / "draft_markers_bootstrap" / "paper" / "method"
    bootstrap_method_root.mkdir(parents=True, exist_ok=True)

    mechanism_keywords = suggest_mechanism_keywords(draft_payload)
    scan_report = run_code2flow_scan(
        project_root=project_root,
        code2flow_root=(code2flow_root or Path("/home/cuihengjia/agent/Ours")).resolve(),
        core_top_k=int(core_top_k),
        annotation_priority="balanced",
        mechanism_keywords=mechanism_keywords,
    )
    coarse_payload = AuthorMarkers.model_validate(
        build_coarse_markers_payload(
            draft_payload=draft_payload,
            scan_report=scan_report,
            project_root=project_root,
        )
    ).model_dump(mode="json")
    coarse_markers_path = _write_markers(method_root / "author_markers.coarse.yaml", coarse_payload)

    llm_config = load_llm_config_from_env(provider=llm_provider, model=llm_model)
    bootstrap_phase1 = {}
    bootstrap_phase2 = {}
    if skip_draft_bootstrap:
        method_code_alignment: dict[str, Any] = {}
        core_snippets: dict[str, Any] = {"snippets": []}
        code_facts: dict[str, Any] | None = None
        refined_payload = validate_author_markers_payload(dict(coarse_payload))
    else:
        _, _, _, _, bootstrap_phase1 = run_phase1_intake(
            project_root=project_root,
            method_root=bootstrap_method_root,
            author_markers_path=str(coarse_markers_path),
            llm_config=llm_config,
            project_id=project_id,
        )
        _, bootstrap_phase2 = run_phase2_analysis(
            project_root=project_root,
            method_root=bootstrap_method_root,
            author_markers_path=str(coarse_markers_path),
            llm_config=llm_config,
            project_id=project_id,
        )

        method_code_alignment, core_snippets, code_facts = _load_bootstrap_artifacts(bootstrap_method_root)
        refined_payload = refine_markers_from_stage12(
            coarse_payload=coarse_payload,
            method_code_alignment=method_code_alignment,
            core_snippets=core_snippets,
            project_root=project_root,
        )
        refined_payload = refine_markers_with_llm(
            refined_payload=refined_payload,
            coarse_payload=coarse_payload,
            method_code_alignment=method_code_alignment,
            core_snippets=core_snippets,
            code_facts=code_facts,
            project_root=project_root,
            llm_config=llm_config,
        )
    refined_markers_path = _write_markers(method_root / "author_markers.story_first.generated.yaml", refined_payload)
    report_path = _write_report(
        method_root / "prepare_report.json",
        project_root=project_root,
        draft_path=draft_path,
        seed_markers_path=coarse_markers_path,
        refined_markers_path=refined_markers_path,
        bootstrap_phase1=bootstrap_phase1,
        bootstrap_phase2=bootstrap_phase2,
        exit_code=0,
        llm_config=llm_config,
        bootstrap_skipped=skip_draft_bootstrap,
    )
    return {
        "exit_code": 0,
        "coarse_markers": coarse_markers_path,
        "final_markers": refined_markers_path,
        "seed_markers": coarse_markers_path,
        "refined_markers": refined_markers_path,
        "bootstrap_root": bootstrap_method_root.parents[2],
        "report": report_path,
    }


def _write_markers(path: Path, payload: dict[str, Any]) -> Path:
    validated = AuthorMarkers.model_validate(payload).model_dump(mode="json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(validated, allow_unicode=True, sort_keys=False), encoding="utf-8")
    path.with_suffix(".json").write_text(json.dumps(validated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _normalize_draft_payload_for_prepare(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    project_goal = str(normalized.get("project_goal") or "").strip()
    if project_goal and not str(normalized.get("paper_method_goal") or "").strip():
        normalized["paper_method_goal"] = project_goal
    if not str(normalized.get("method_mainline") or "").strip():
        step_names = [
            str(step.get("name") or "").strip()
            for step in normalized.get("pipeline_steps") or []
            if isinstance(step, dict) and str(step.get("name") or "").strip()
        ]
        if step_names:
            normalized["method_mainline"] = step_names
        elif project_goal:
            normalized["method_mainline"] = project_goal
    return normalized


def _write_report(
    path: Path,
    *,
    project_root: Path,
    draft_path: Path,
    seed_markers_path: Path,
    refined_markers_path: Path | None,
    bootstrap_phase1: dict[str, Path],
    bootstrap_phase2: dict[str, Path],
    exit_code: int,
    llm_config: Any,
    bootstrap_skipped: bool,
) -> Path:
    payload = {
        "project_root": str(project_root),
        "draft_path": str(draft_path),
        "seed_markers_path": str(seed_markers_path),
        "refined_markers_path": str(refined_markers_path) if refined_markers_path else "",
        "bootstrap": {
            "skipped": bool(bootstrap_skipped),
            "llm_provider": getattr(getattr(llm_config, "provider", None), "value", "none"),
            "llm_model": getattr(llm_config, "model", "") or "",
            "phase1_manifest": str(bootstrap_phase1.get("phase1_manifest", "")),
            "phase2_manifest": str(bootstrap_phase2.get("phase2_manifest", "")),
            "evidence_raw": str(bootstrap_phase1.get("evidence_raw", "")),
            "alignment": str(bootstrap_phase2.get("alignment", "")),
        },
        "exit_code": int(exit_code),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _load_bootstrap_artifacts(method_root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    alignment = _read_json(method_output(method_root, "intake_alignment"))
    snippets = _read_json(method_output(method_root, "snippets"))
    facts = _read_json(method_output(method_root, "facts"))
    core_snippets = snippets if isinstance(snippets, dict) else {"snippets": []}
    code_facts = facts if isinstance(facts, dict) else None
    return alignment, core_snippets, code_facts


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _collect_paths_from_file(path: Path, *, project_root: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return _collect_paths(payload, project_root=project_root)


def _collect_paths(payload: Any, *, project_root: Path) -> list[str]:
    found: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"path", "file", "file_path", "source_path"} and isinstance(item, str):
                    normalized = _normalize_repo_path(item, project_root=project_root)
                    if normalized:
                        found.append(normalized)
                else:
                    visit(item)
            return
        if isinstance(value, list):
            for item in value:
                visit(item)

    visit(payload)
    return _merge_unique(found)


def _normalize_repo_path(path_text: str, *, project_root: Path) -> str:
    raw = str(path_text or "").strip()
    if not raw:
        return ""
    candidate = Path(raw)
    if candidate.is_absolute():
        try:
            return candidate.resolve().relative_to(project_root.resolve()).as_posix()
        except ValueError:
            return ""
    return candidate.as_posix()


def _collect_step_names(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    names: list[str] = []
    for step in payload.get("pipeline_steps", []) if isinstance(payload, dict) else []:
        if not isinstance(step, dict):
            continue
        text = str(step.get("name") or "").strip()
        if text:
            names.append(text)
    return _merge_unique(names)


def _missing_repo_files(payload: dict[str, Any], *, project_root: Path) -> list[str]:
    candidate_paths: list[str] = []
    candidate_paths.extend(str(item) for item in payload.get("priority_files") or [])
    for role in payload.get("module_roles") or []:
        if isinstance(role, dict):
            candidate_paths.append(str(role.get("path") or ""))
    for step in payload.get("pipeline_steps") or []:
        if isinstance(step, dict):
            candidate_paths.extend(str(item) for item in step.get("related_files") or [])
    missing: list[str] = []
    for rel_path in _merge_unique(candidate_paths):
        if not rel_path or rel_path.startswith("__auto_generated__/"):
            continue
        if not (project_root / rel_path).exists():
            missing.append(rel_path)
    return missing


def _dedupe_mismatches(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[str, ...], str]] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        description = str(item.get("description") or "").strip()
        files = tuple(sorted(str(value).strip() for value in item.get("files") or [] if str(value).strip()))
        severity = str(item.get("severity") or "medium").strip() or "medium"
        if not description:
            continue
        key = (description, files, severity)
        if key in seen:
            continue
        seen.add(key)
        out.append({"description": description, "files": list(files), "severity": severity})
    return out


def _merge_unique(*groups: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            out.append(text)
    return out


if __name__ == "__main__":
    raise SystemExit(main())
