from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScanConfig:
    include_exts: tuple[str, ...] = (
        ".py",
        ".ipynb",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".java",
        ".cpp",
        ".cc",
        ".c",
        ".h",
        ".hpp",
        ".go",
        ".rs",
        ".m",
        ".mm",
        ".sh",
    )
    ignore_dirs: tuple[str, ...] = (
        ".git",
        ".idea",
        ".vscode",
        "__pycache__",
        "node_modules",
        "dist",
        "build",
        "target",
        ".venv",
        "venv",
        "site-packages",
        ".mypy_cache",
        ".pytest_cache",
        "pretrained_weight",
        "swark-output",
        "outputs",
        "checkpoints",
    )
    max_file_bytes: int = 220_000
    max_snippet_chars: int = 2200
    max_context_files: int = 18
    core_top_k: int = 12


ENTRYPOINT_NAME_HINTS: tuple[str, ...] = (
    "main",
    "train",
    "eval",
    "run",
    "inference",
    "predict",
    "serve",
    "cli",
)


TOUCHPOINT_PATTERNS: dict[str, tuple[str, ...]] = {
    "data": ("dataset", "dataloader", "load_data", "preprocess", "tokenize"),
    "model": ("model", "network", "backbone", "encoder", "decoder", "forward"),
    "objective": ("loss", "criterion", "objective", "regulariz"),
    "optimize": ("optimizer", "scheduler", "backward", "step("),
    "eval": ("metric", "evaluate", "validation", "test_step", "inference"),
    "config": ("argparse", "yaml", "toml", "config", "hydra"),
}
