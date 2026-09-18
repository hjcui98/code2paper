"""复用证据来源索引：区分"本次 run 产生"与"从冻结根复制的"invocation 回执。

回放/恢复会把冻结 Formalizer 阶段的 invocation 回执整目录复制进新的 run 根。若不标注
来源，任何"按回执求和"的口径（token 用量、效率指标、接受率）都会把历史数据记成这次
run 的——§14.3 的效率维度与 prepared 根续跑所依赖的"这次尝试是否真的发过请求"
都依赖这一区分。

索引内容只有路径与复制时摘要，因此可以被复算：内容被改写（摘要不符）时不再算复用。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

__all__ = [
    "REUSED_EVIDENCE_RECEIPTS_FILENAME",
    "reused_evidence_index_path",
    "write_reused_evidence_index",
    "load_reused_evidence_index",
    "classify_receipt",
    "normalize_relative",
]

#: 与 `token_usage_summary_v1.json` 同目录，便于就地对照。
REUSED_EVIDENCE_RECEIPTS_FILENAME = "reused_evidence_receipts_v1.json"


def _authoring_dir(out_root: str | Path) -> Path:
    return Path(out_root) / "artifacts" / "06_authoring"


def reused_evidence_index_path(out_root: str | Path) -> Path:
    return _authoring_dir(out_root) / REUSED_EVIDENCE_RECEIPTS_FILENAME


def _digest_file(path: Path) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_reused_evidence_index(
    *,
    root: str | Path,
    frozen_root: str | Path,
    ledger_dir: str | Path,
    relative_paths: Iterable[str],
) -> Path:
    """写出 ``相对路径 -> 复制时摘要`` 索引（``root`` 是 run 根，``ledger_dir`` 是回执目录）。"""

    ledger = Path(ledger_dir)
    payload = {
        "schema_version": "1.0",
        "artifact": REUSED_EVIDENCE_RECEIPTS_FILENAME.removesuffix(".json"),
        "source": "frozen_formalizer_phase",
        "frozen_root": str(frozen_root),
        "receipts": [
            {
                "path": relative,
                "digest": _digest_file(ledger / relative),
            }
            for relative in relative_paths
            if (ledger / relative).is_file()
        ],
    }
    path = reused_evidence_index_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def load_reused_evidence_index(out_root: str | Path) -> dict[str, str]:
    """读取索引；文件缺失/不可解析时返回空映射（等价于"全部算本次产生"）。"""

    path = reused_evidence_index_path(out_root)
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(payload, Mapping):
        return {}
    index: dict[str, str] = {}
    for entry in payload.get("receipts") or ():
        if not isinstance(entry, Mapping):
            continue
        relative = str(entry.get("path") or "").strip()
        digest = str(entry.get("digest") or "").strip()
        if relative and digest:
            index[relative] = digest
    return index


def classify_receipt(
    *, index: Mapping[str, str], relative_path: str, receipt_path: str | Path
) -> bool:
    """索引声明为复制且内容仍与复制时一致 → True（复用证据）。"""

    expected = str(index.get(relative_path) or "")
    if not expected:
        return False
    path = Path(receipt_path)
    if not path.is_file():
        return False
    return expected == _digest_file(path)


def normalize_relative(path: str | Path, base: str | Path) -> str:
    return str(Path(path).relative_to(Path(base))).replace(os.sep, "/")
