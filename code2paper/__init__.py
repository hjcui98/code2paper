"""Repo-root package shim for running the src-layout package without installation.

This lets commands like `python -m code2paper.cli.run` work directly from the
repository root, while keeping the real implementation under `src/code2paper`.
"""

from __future__ import annotations

from pathlib import Path


_ROOT_PACKAGE_DIR = Path(__file__).resolve().parent
_SRC_PACKAGE_DIR = _ROOT_PACKAGE_DIR.parent / "src" / "code2paper"

__path__ = [str(_ROOT_PACKAGE_DIR)]
if _SRC_PACKAGE_DIR.is_dir():
    __path__.append(str(_SRC_PACKAGE_DIR))

_SRC_INIT = _SRC_PACKAGE_DIR / "__init__.py"
if _SRC_INIT.is_file():
    exec(compile(_SRC_INIT.read_text(encoding="utf-8"), str(_SRC_INIT), "exec"), globals(), globals())
