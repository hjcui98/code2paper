"""Run-level reproducibility manifest helpers."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from code2paper.schemas import ArtifactHash, Code2PaperRunManifest, LLMConfig, ReadmePolicy


def hash_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def hash_text(payload: str) -> str:
    return hash_bytes(payload.encode("utf-8"))


def hash_file(path: str | Path) -> str:
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        return ""
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def hash_json_payload(payload: object) -> str:
    return hash_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def hash_project_tree(project_root: str | Path) -> str:
    root = Path(project_root)
    if not root.exists():
        return ""
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if _is_ignored_path(path):
            continue
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hash_file(path).encode("utf-8"))
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def build_run_manifest(
    *,
    project_root: str | Path,
    readme_policy: ReadmePolicy = ReadmePolicy.EXCLUDE,
    author_input_path: str | Path | None = None,
    llm: LLMConfig | None = None,
    phase_inputs: dict[str, list[str]] | None = None,
    output_paths: dict[str, str | Path] | None = None,
    final_draft_path: str | Path | None = None,
    validator_reports: list[str] | None = None,
    agentic_budgets: dict[str, int] | None = None,
) -> Code2PaperRunManifest:
    outputs = {
        name: ArtifactHash(path=str(path), hash=hash_file(path))
        for name, path in (output_paths or {}).items()
    }
    final_draft_hash = hash_file(final_draft_path) if final_draft_path is not None else ""
    created_at = datetime.now(timezone.utc).isoformat()
    project_hash = hash_project_tree(project_root)
    run_id = _run_id(project_hash=project_hash, created_at=created_at, output_paths=output_paths or {})
    author_input_hash = hash_file(author_input_path) if author_input_path else ""
    return Code2PaperRunManifest(
        run_id=run_id,
        created_at=created_at,
        project_root=str(project_root),
        project_hash=project_hash,
        readme_policy=readme_policy,
        author_input_hash=author_input_hash,
        llm=llm or LLMConfig(),
        phase_inputs=phase_inputs or {},
        phase_outputs=outputs,
        final_draft_hash=final_draft_hash,
        validator_reports=validator_reports or [],
        agentic_budgets=agentic_budgets or {},
    )


def write_run_manifest(path: str | Path, manifest: Code2PaperRunManifest) -> None:
    manifest_path = Path(path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _run_id(*, project_hash: str, created_at: str, output_paths: dict[str, str | Path]) -> str:
    payload = {
        "project_hash": project_hash,
        "created_at": created_at,
        "outputs": {name: str(path) for name, path in sorted(output_paths.items())},
    }
    return "RUN-" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]


def _is_ignored_path(path: Path) -> bool:
    parts = set(path.parts)
    ignored_dirs = {
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
        "checkpoints",
        "checkpoint",
        "logs",
        "wandb",
    }
    if parts & ignored_dirs:
        return True
    return path.suffix in {".pyc", ".pyo", ".pt", ".pth", ".ckpt", ".bin"}
