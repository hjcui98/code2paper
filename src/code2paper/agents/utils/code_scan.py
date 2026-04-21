from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass
class ScanBudgets:
    max_total_files: int = 80
    max_total_bytes: int = 10 * 1024 * 1024
    max_single_file_bytes: int = 512 * 1024


def scan_repo(
    repo_path: str,
    filters: Optional[Dict[str, Any]] = None,
    budgets: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    root = Path(repo_path).expanduser().resolve()
    filter_cfg = filters or {}
    budget_cfg = budgets or {}

    budgets_obj = ScanBudgets(
        max_total_files=int(budget_cfg.get("max_total_files", 80)),
        max_total_bytes=int(budget_cfg.get("max_total_bytes", 10 * 1024 * 1024)),
        max_single_file_bytes=int(budget_cfg.get("max_single_file_bytes", 512 * 1024)),
    )

    excluded_dirs = set(filter_cfg.get("excluded_dirs") or [
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        "build",
        "dist",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "output",
        "hf",
    ])

    excluded_exts = set(filter_cfg.get("excluded_exts") or [
        ".pt",
        ".pth",
        ".ckpt",
        ".onnx",
        ".bin",
        ".safetensors",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".mp4",
        ".mov",
        ".pdf",
        ".zip",
        ".tar",
        ".gz",
        ".7z",
    ])

    include_exts = set(filter_cfg.get("include_exts") or [
        ".py",
        ".ipynb",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".java",
        ".cpp",
        ".cc",
        ".c",
        ".h",
        ".hpp",
        ".go",
        ".rs",
        ".yaml",
        ".yml",
        ".json",
        ".toml",
        ".ini",
        ".cfg",
        ".sh",
        ".md",
    ])

    files: List[Dict[str, Any]] = []
    warnings: List[str] = []
    errors: List[str] = []

    total_files = 0
    total_bytes = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dir_rel = os.path.relpath(dirpath, root)
        parts = [] if dir_rel == "." else dir_rel.split(os.sep)
        if any(p in excluded_dirs for p in parts):
            dirnames[:] = []
            continue

        dirnames[:] = [d for d in dirnames if d not in excluded_dirs]

        for filename in filenames:
            path = Path(dirpath) / filename
            ext = path.suffix.lower()

            if ext and ext in excluded_exts:
                continue
            if ext and include_exts and ext not in include_exts:
                continue

            try:
                st = path.stat()
            except Exception as e:
                errors.append(f"stat_failed:{path}:{e}")
                continue

            if st.st_size > budgets_obj.max_single_file_bytes:
                warnings.append(f"oversized_file:{str(path)}:{st.st_size}")
                continue

            if total_files + 1 > budgets_obj.max_total_files:
                warnings.append("budget_stop:max_total_files")
                dirnames[:] = []
                break

            if total_bytes + st.st_size > budgets_obj.max_total_bytes:
                warnings.append("budget_stop:max_total_bytes")
                dirnames[:] = []
                break

            language = _infer_language(ext)
            kind = _infer_kind(path, language)
            sha1 = _sha1_file(path)

            files.append({
                "path": str(path),
                "ext": ext,
                "language": language,
                "size_bytes": st.st_size,
                "sha1": sha1,
                "kind": kind,
            })

            total_files += 1
            total_bytes += st.st_size

        if total_files >= budgets_obj.max_total_files or total_bytes >= budgets_obj.max_total_bytes:
            break

    return {
        "meta": {
            "repo_id": _sha1_str(str(root)),
            "root_path": str(root),
            "filters": {"excluded_dirs": sorted(excluded_dirs), "excluded_exts": sorted(excluded_exts), "include_exts": sorted(include_exts)},
            "scan_stats": {
                "max_total_files": budgets_obj.max_total_files,
                "max_total_bytes": budgets_obj.max_total_bytes,
                "max_single_file_bytes": budgets_obj.max_single_file_bytes,
                "scanned_files": total_files,
                "scanned_bytes": total_bytes,
            },
        },
        "project_files": files,
        "repo_structure_hints": _build_repo_structure_hints(files),
        "errors": errors,
        "warnings": warnings,
    }


def select_candidate_files(
    file_index: List[Dict[str, Any]],
    keyword_bank: List[str],
    top_k: int = 60,
) -> List[Dict[str, Any]]:
    scored: List[Tuple[float, Dict[str, Any]]] = []
    bank = [k.lower() for k in keyword_bank if k and len(k) >= 3][:200]
    signal_terms = [
        "def forward",
        "class",
        "nn.module",
        "torch",
        "dataset",
        "dataloader",
        "optimizer",
        "backward",
        "criterion",
        "loss",
        "augment",
        "transforms",
        "infer",
        "evaluate",
        "metric",
        "argparse",
        "yaml",
    ]

    for f in file_index:
        path = f.get("path")
        if not path:
            continue
        try:
            content = Path(path).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        sample = content[:20000].lower()
        signal_hits = sum(1 for s in signal_terms if s in sample)
        kw_hits = sum(1 for k in bank if k in sample)
        score = signal_hits * 2.0 + min(kw_hits, 50) * 0.1

        name = Path(path).name.lower()
        if "train" in name:
            score += 1.0
        if "model" in name:
            score += 1.0
        if "config" in name:
            score += 0.5

        scored.append((score, f))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [f for _, f in scored[: max(1, top_k)]]


def read_file_lines(path: str, max_bytes: int = 512 * 1024) -> Optional[List[str]]:
    p = Path(path)
    try:
        st = p.stat()
        if st.st_size > max_bytes:
            return None
    except Exception:
        return None

    try:
        text = p.read_text(encoding="utf-8", errors="ignore")
        return text.splitlines()
    except Exception:
        return None


def _infer_language(ext: str) -> str:
    return {
        ".py": "python",
        ".ipynb": "json",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".java": "java",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".c": "c",
        ".h": "c",
        ".hpp": "cpp",
        ".go": "go",
        ".rs": "rust",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
        ".toml": "toml",
        ".ini": "ini",
        ".cfg": "ini",
        ".sh": "shell",
        ".md": "markdown",
    }.get(ext, "unknown")


def _infer_kind(path: Path, language: str) -> str:
    name = path.name.lower()
    if language in {"yaml", "json", "toml", "ini"}:
        return "config"
    if "test" in name:
        return "test"
    if language == "python" and name == "__init__.py":
        return "package_init"
    return "source" if language not in {"unknown"} else "other"


def _sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 64)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _sha1_str(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def _build_repo_structure_hints(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    def score_path(p: str) -> float:
        name = Path(p).name.lower()
        score = 0.0
        if any(k in name for k in ["train", "main", "run"]):
            score += 1.0
        if any(k in name for k in ["model", "net", "backbone", "encoder", "decoder"]):
            score += 1.0
        if any(k in name for k in ["data", "dataset", "loader"]):
            score += 0.8
        if any(k in name for k in ["eval", "metric", "test"]):
            score += 0.6
        if any(k in name for k in ["config", "cfg", "yaml", "yml"]):
            score += 0.4
        return score

    buckets = {
        "entry_candidates": [],
        "model_files_candidates": [],
        "training_files_candidates": [],
        "data_pipeline_candidates": [],
    }

    for f in files:
        p = f.get("path")
        if not p:
            continue
        s = score_path(p)
        if s <= 0:
            continue
        name = Path(p).name.lower()
        record = {"path": p, "reason": "name_signal", "score": round(s, 2)}
        if any(k in name for k in ["main", "run", "train"]):
            buckets["entry_candidates"].append(record)
        if any(k in name for k in ["model", "net", "backbone", "encoder", "decoder"]):
            buckets["model_files_candidates"].append(record)
        if any(k in name for k in ["train", "optim", "scheduler"]):
            buckets["training_files_candidates"].append(record)
        if any(k in name for k in ["data", "dataset", "loader"]):
            buckets["data_pipeline_candidates"].append(record)

    for k in buckets:
        buckets[k].sort(key=lambda x: x["score"], reverse=True)
        buckets[k] = buckets[k][:20]

    return buckets

