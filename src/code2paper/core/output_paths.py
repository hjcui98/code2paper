from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re


def default_out_root(
    project_root: str | Path,
    *,
    intent_path: str | Path | None = None,
    base_dir: str | Path | None = None,
    now: datetime | None = None,
) -> Path:
    repo_name = preferred_output_name(project_root, intent_path=intent_path)
    stamp = (now or datetime.now().astimezone()).strftime("%Y%m%d_%H%M%S")
    root = Path(base_dir) if base_dir is not None else Path.cwd()
    return root / "outputs" / f"{repo_name}_{stamp}"


def resolve_out_root(
    out_root: str | Path | None,
    *,
    project_root: str | Path,
    intent_path: str | Path | None = None,
    base_dir: str | Path | None = None,
    now: datetime | None = None,
) -> Path:
    raw = str(out_root or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return default_out_root(project_root, intent_path=intent_path, base_dir=base_dir, now=now).expanduser().resolve()


def repo_output_name(project_root: str | Path) -> str:
    name = Path(project_root).expanduser().resolve().name.strip()
    return _slugify_name(name) or "project"


def preferred_output_name(project_root: str | Path, *, intent_path: str | Path | None = None) -> str:
    intent_slug = intent_output_name(intent_path)
    if intent_slug:
        return intent_slug
    return repo_output_name(project_root)


def resolve_project_id(
    project_id: str | None,
    *,
    project_root: str | Path,
    intent_path: str | Path | None = None,
) -> str:
    explicit = str(project_id or "").strip()
    if explicit:
        return explicit
    return preferred_output_name(project_root, intent_path=intent_path)


def intent_output_name(intent_path: str | Path | None) -> str:
    raw = str(intent_path or "").strip()
    if not raw:
        return ""
    stem = Path(raw).expanduser().name
    if stem.lower().endswith(".yaml"):
        stem = stem[:-5]
    elif stem.lower().endswith(".yml"):
        stem = stem[:-4]
    stem = re.sub(r"\s+-\s+", "_", stem)
    stem = re.sub(r"[\s._-]+$", "", stem)
    return _slugify_name(stem)


def _slugify_name(name: str) -> str:
    text = str(name or "").strip()
    if not text:
        return ""
    return re.sub(r"[^0-9A-Za-z._-]+", "_", text).strip("._-")
