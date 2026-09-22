"""自洽的研究导入 checkpoint fixture（供 PR A/B/C 回归使用）。

以冻结事故归档的 `research_stage_checkpoint_v1.json` 为基，按需改写字段并**重新封装**
每个内联产物的 `content_digest`（这些模型在缺 digest 时会自行计算），因此生成的文件是
"内容与摘要自洽"的真实形状，而不是空壳 JSON——空壳正是审计 §A.4 要求拒绝的对象。
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import incident_archive

RESEARCH_CHECKPOINT_RELATIVE = (
    "artifacts/research_product/research_stage_checkpoint_v1.json"
)


def archive_checkpoint_path() -> Path:
    return incident_archive.archive_root() / RESEARCH_CHECKPOINT_RELATIVE


def _seal_artifacts(payload: dict[str, Any], original: Mapping[str, Any]) -> None:
    """只重新封装**被改写**的内联产物；未改动的保留原始摘要。

    有些模型（如 `AtomicClaimSetV3`）的 `content_digest` 是必填字段且带有依赖链
    （packets→facts→claims），不能凭空重算；只对本次真正改写过的产物做重新封装，
    其余保持归档原值，fixture 因此仍是"内容与摘要自洽"的真实形状。
    """

    from code2paper.agentic.authoring_execution_identity import (
        RESEARCH_IMPORT_REQUIRED_ARTIFACTS,
    )

    for key, module_name, class_name in RESEARCH_IMPORT_REQUIRED_ARTIFACTS:
        artifact = payload.get(key)
        if not isinstance(artifact, Mapping):
            continue
        if dict(artifact) == dict(original.get(key) or {}):
            continue
        model = getattr(importlib.import_module(module_name), class_name)
        rebuilt = dict(artifact)
        rebuilt.pop("content_digest", None)
        try:
            validated = model.model_validate(rebuilt)
        except Exception:
            # 该模型要求显式 digest：保留原值，避免伪造成"自洽"。
            rebuilt["content_digest"] = str(artifact.get("content_digest") or "")
            validated = model.model_validate(rebuilt)
        payload[key] = json.loads(validated.model_dump_json())


def write_research_checkpoint(
    destination: Path,
    *,
    project_tree_hash: str | None = None,
    repo_snapshot_id: str | None = None,
    run_id: str | None = None,
    drop: Iterable[str] = (),
    extra: Mapping[str, Any] | None = None,
    corrupt_digest: Iterable[str] = (),
    unsafe_path: str | None = None,
    seal: bool = True,
) -> Path:
    """生成一份（默认）自洽的 checkpoint；各参数用于构造负面用例。"""

    payload: dict[str, Any] = json.loads(archive_checkpoint_path().read_text(encoding="utf-8"))
    original: dict[str, Any] = json.loads(json.dumps(payload))
    if project_tree_hash is not None:
        payload["project_tree_hash"] = project_tree_hash
        manifest = payload.get("source_manifest")
        if isinstance(manifest, dict):
            manifest["project_tree_hash"] = project_tree_hash
    if repo_snapshot_id is not None:
        payload["repo_snapshot_id"] = repo_snapshot_id
        manifest = payload.get("source_manifest")
        if isinstance(manifest, dict):
            manifest["repo_snapshot_id"] = repo_snapshot_id
    if run_id is not None:
        payload["run_id"] = run_id
    for key in drop:
        payload.pop(key, None)
    if extra:
        payload.update(dict(extra))
    if unsafe_path is not None:
        manifest = payload.get("source_manifest")
        if isinstance(manifest, dict):
            entries = manifest.get("entries")
            if isinstance(entries, list) and entries:
                entries[0] = {**entries[0], "path": unsafe_path}
    if seal:
        _seal_artifacts(payload, original)
    for key in corrupt_digest:
        artifact = payload.get(key)
        if isinstance(artifact, dict):
            artifact["content_digest"] = "sha256:" + "0" * 64
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return destination


def matching_tree_hash(target_repo: str | Path) -> str:
    """目标仓库当前内容的 tree hash（用于生成与其匹配的 checkpoint）。"""

    from code2paper.agentic.authoring_execution_identity import capture_target_identity

    return capture_target_identity(target_repo).project_tree_hash
