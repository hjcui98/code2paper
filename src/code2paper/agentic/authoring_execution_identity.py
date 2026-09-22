"""Authoring execution identity and run-open admission (WP1).

方案 `docs/code2paper_repair_execution_20260917.md` §5：一次执行必须有明确的
身份，且"新实验 / 同身份恢复 / 导入研究证据后重新写作"三者不能互相冒充。

本模块只做三件事：

1. **引擎内容指纹**（`capture_engine_source_snapshot`）：Code2Paper 自身的
   commit + 未提交内容的逐文件内容哈希。旧的 porcelain 状态摘要无法区分
   "同一路径仍为 M，但内容已变"，因此不能用作恢复兼容性判断。
2. **执行身份 V2**（`AuthoringExecutionIdentityV2`）：把引擎身份、目标仓库
   身份、作者意图/claims/profile/model/prompt/tokenizer/validator 摘要分开，
   不再让 `code_commit_sha` 同时冒充两者（事故 §1.2）。
3. **目录准入与租约**（`validate_run_open` / `acquire_run_lease`）：new 拒绝
   非空目录、resume 逐字段比较、已耗尽 invocation 直接阻断、fork 只导入可
   验证的研究证据；同一 run 只允许一个写者。

历史对象不被改写（不变量 I8）：本模块不触碰 `run_identity_v1.json`、
ledger、旧 plan/manifest；它新增自己的身份文件并按需只读旧文件。
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.digest import digest_json


RunOpenMode = Literal["auto", "new", "resume", "fork_authoring"]
CreationMode = Literal["new", "fork_authoring"]

#: 目录准入错误码（方案 §5.3）。
RUN_DIRECTORY_NOT_EMPTY = "run_directory_not_empty"
RESUME_IDENTITY_MISSING = "resume_identity_missing"
RESUME_IDENTITY_MISMATCH = "resume_identity_mismatch"
RESUME_IDENTITY_LEGACY = "resume_identity_legacy_incompatible"
RESUME_ENGINE_UNAVAILABLE = "resume_engine_identity_unavailable"
RESUME_EXHAUSTED_INVOCATION = "resume_exhausted_invocation"
RESEARCH_IMPORT_UNVERIFIABLE = "research_import_unverifiable"
#: 目标 source snapshot 不可用（审计 §A.1.4）：不得用"错误状态也有 sha256"伪装身份。
TARGET_SNAPSHOT_UNAVAILABLE = "target_snapshot_unavailable"
#: 验收规则来源不可用（审计 §A.1.5）：非空 digest 不等于可用 bundle。
VALIDATOR_BUNDLE_UNAVAILABLE = "validator_bundle_unavailable"
ENGINE_SNAPSHOT_UNSTABLE = "engine_snapshot_unstable"
ENGINE_ROOT_UNRESOLVED = "engine_root_unresolved"
RUN_LEASE_HELD = "run_lease_held"
RUN_LEASE_FILE = ".run_lease.lock"

#: 进程内已持有的租约：跨进程互斥、进程内幂等（见 RunLease 文档）。
_HELD_LEASES: dict[str, "RunLease"] = {}

#: 不变量 I10：参与"验收规则身份"的**封闭**文件集合。任何改变验收语义的修改都必须
#: 落在其中之一，从而改变 validator bundle digest——历史 accepted/rejected 不得在同一个
#: receipt digest 名义下被重新解释。刻意只收 contract 层模块：把整个 writer 收进来会让
#: 任何重构都使 resume 失效（过度触发虽然安全，但会让身份失去区分度）。
VALIDATOR_BUNDLE_SOURCES: tuple[str, ...] = (
    "src/code2paper/agentic/publication_transaction_contract.py",
    "src/code2paper/agentic/writer_output_workload.py",
    "src/code2paper/agentic/unified_context_compiler.py",
    "src/code2paper/agentic/mechanism_context_pages.py",
    "src/code2paper/agentic/writer_attempt_ledger.py",
    "src/code2paper/agentic/authoring_artifact_index.py",
    "src/code2paper/agentic/paragraph_prose_composer.py",
)

#: 引擎指纹排除项：运行产物、缓存、密钥、数据库不进身份（方案 §5.2）。
_ENGINE_EXCLUDED_PREFIXES: tuple[str, ...] = (
    "artifacts/",
    ".tmp/",
    "tmp/",
    "output/",
    "outputs/",
    "results/",
    "logs/",
    ".live-runs/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
    ".agent-team/",
    ".omo/",
    ".opencode/",
    "datasets/",
    "checkpoints/",
    "checkpoint/",
    "vendor/",
    "node_modules/",
)
_ENGINE_EXCLUDED_SUFFIXES: tuple[str, ...] = (
    ".pyc",
    ".pyo",
    ".log",
    ".sqlite",
    ".sqlite3",
    ".tmp",
    ".temp",
)
_ENGINE_EXCLUDED_NAMES: tuple[str, ...] = (".env", RUN_LEASE_FILE)
_ENGINE_EXCLUDED_SEGMENTS: tuple[str, ...] = ("__pycache__", ".git")


def _is_excluded_engine_path(relative: str) -> bool:
    normalized = relative.replace(os.sep, "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = normalized.lstrip("/")
    if not normalized:
        return True
    if normalized.startswith(_ENGINE_EXCLUDED_PREFIXES):
        return True
    segments = normalized.split("/")
    if any(segment in _ENGINE_EXCLUDED_SEGMENTS for segment in segments):
        return True
    if segments[-1] in _ENGINE_EXCLUDED_NAMES:
        return True
    if normalized == ".env" or normalized.startswith(".env."):
        return True
    return normalized.endswith(_ENGINE_EXCLUDED_SUFFIXES)


def _run_git(root: Path, *args: str) -> tuple[int, str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except Exception:
        # git 探测永远不能让准入崩溃：拿不到就如实报告"不可用"。
        return 1, ""
    return result.returncode, result.stdout


def resolve_engine_root(start: str | Path | None = None) -> Path | None:
    """定位 Code2Paper 引擎根目录（含 ``pyproject.toml`` 与 ``src/code2paper``）。"""

    candidate = (
        Path(start).expanduser().resolve()
        if start is not None
        else Path(__file__).resolve()
    )
    for root in (candidate, *candidate.parents):
        if (root / "pyproject.toml").is_file() and (root / "src" / "code2paper").is_dir():
            return root
    return None


@dataclass(frozen=True)
class EngineDirtyEntry:
    path: str
    status: str
    kind: str
    digest: str = ""

    def as_payload(self) -> dict[str, str]:
        payload = {"path": self.path, "status": self.status, "kind": self.kind}
        if self.digest:
            payload["digest"] = self.digest
        return payload


@dataclass(frozen=True)
class ValidatorBundleSnapshot:
    """验收规则身份（I10）：validator/contract 层源码的逐文件内容指纹。"""

    digest: str
    engine_root: str
    entries: tuple[tuple[str, str], ...] = ()
    missing: tuple[str, ...] = ()
    failure_code: str = ""

    @property
    def is_usable(self) -> bool:
        return not self.failure_code

    def as_diagnostics(self) -> dict[str, Any]:
        return {
            "digest": self.digest,
            "engine_root": self.engine_root,
            "source_count": len(self.entries),
            "missing": list(self.missing),
            "failure_code": self.failure_code,
        }


@dataclass(frozen=True)
class EngineSourceSnapshot:
    """Code2Paper 引擎身份：commit + 未提交内容的逐文件内容指纹。"""

    engine_root: str
    commit_sha: str
    branch: str
    source_digest: str
    entries: tuple[EngineDirtyEntry, ...] = ()
    excluded_count: int = 0
    unstable: bool = False
    failure_code: str = ""

    @property
    def is_usable(self) -> bool:
        return not self.failure_code and self.commit_sha != "unknown"

    def as_diagnostics(self) -> dict[str, Any]:
        return {
            "engine_root": self.engine_root,
            "commit_sha": self.commit_sha,
            "branch": self.branch,
            "source_digest": self.source_digest,
            "dirty_entry_count": len(self.entries),
            "excluded_count": self.excluded_count,
            "unstable": self.unstable,
            "failure_code": self.failure_code,
        }


def _parse_porcelain_z(raw: str) -> list[tuple[str, str]]:
    """解析 ``git status --porcelain=v1 -z``，返回 (status, path) 列表。"""

    parts = [item for item in raw.split("\0") if item]
    entries: list[tuple[str, str]] = []
    index = 0
    while index < len(parts):
        item = parts[index]
        index += 1
        if len(item) < 4:
            continue
        status = item[:2]
        path = item[3:]
        # rename/copy 会额外跟一个原路径条目
        if status[:1] in {"R", "C"} and index < len(parts):
            index += 1
        entries.append((status, path))
    return entries


def _hash_file(path: Path) -> tuple[str, bool]:
    """返回 (sha256 或特殊标记, 读取期间是否不稳定)。"""

    try:
        before = path.stat()
    except OSError:
        return "missing", False
    if path.is_symlink():
        try:
            return f"symlink:{os.readlink(path)}", False
        except OSError:
            return "symlink:unknown", False
    if not path.is_file():
        return "not-a-file", False
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        after = path.stat()
    except OSError:
        return "unreadable", True
    unstable = (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns)
    return "sha256:" + digest.hexdigest(), unstable


def capture_engine_source_snapshot(
    engine_root: str | Path | None = None,
) -> EngineSourceSnapshot:
    """内容寻址的引擎指纹；无法解析引擎根时返回带 failure_code 的快照。"""

    root = resolve_engine_root(engine_root)
    if root is None:
        return EngineSourceSnapshot(
            engine_root=str(engine_root or ""),
            commit_sha="unknown",
            branch="",
            source_digest="",
            failure_code=ENGINE_ROOT_UNRESOLVED,
        )

    code, head = _run_git(root, "rev-parse", "HEAD")
    commit_sha = head.strip() if code == 0 and head.strip() else "unknown"
    code, branch_out = _run_git(root, "rev-parse", "--abbrev-ref", "HEAD")
    branch = branch_out.strip() if code == 0 else ""

    code, raw_status = _run_git(
        root, "status", "--porcelain=v1", "-z", "--untracked-files=all"
    )
    if code != 0:
        return EngineSourceSnapshot(
            engine_root=str(root),
            commit_sha=commit_sha,
            branch=branch,
            source_digest="",
            failure_code=ENGINE_SNAPSHOT_UNSTABLE,
        )

    entries: list[EngineDirtyEntry] = []
    excluded = 0
    unstable = False
    for status, raw_path in _parse_porcelain_z(raw_status):
        relative = raw_path.replace(os.sep, "/")
        if _is_excluded_engine_path(relative):
            excluded += 1
            continue
        absolute = root / raw_path
        if "D" in status and not absolute.exists():
            entries.append(EngineDirtyEntry(relative, status, "deleted"))
            continue
        digest, file_unstable = _hash_file(absolute)
        unstable = unstable or file_unstable
        kind = "symlink" if digest.startswith("symlink:") else "file"
        entries.append(EngineDirtyEntry(relative, status, kind, digest))

    entries.sort(key=lambda item: item.path)
    payload = {
        "schema_version": "1.0",
        "commit_sha": commit_sha,
        "entries": [item.as_payload() for item in entries],
    }
    return EngineSourceSnapshot(
        engine_root=str(root),
        commit_sha=commit_sha,
        branch=branch,
        source_digest=digest_json(payload),
        entries=tuple(entries),
        excluded_count=excluded,
        unstable=unstable,
        failure_code=ENGINE_SNAPSHOT_UNSTABLE if unstable else "",
    )


class BirthMetadataV1(BaseModel):
    """执行的**出生信息**：由创建动作决定，之后 resume 只继承、不重造（审计 §A.2）。

    ``run_open_mode`` 是"本次打开动作"（new/resume/auto/fork）；``creation_mode`` 是
    "这次执行出生时是什么"。旧实现让 resume 动作重新推导出生信息，于是合法的 fork
    执行一旦 resume 就因 ``creation_mode`` 不匹配被拒（审计 F03 已复现）。
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    creation_mode: CreationMode = "new"
    parent_execution_id: str | None = None
    research_import_digest: str | None = None

    @property
    def is_fork(self) -> bool:
        return self.creation_mode == "fork_authoring"


class AuthoringExecutionIdentityV2(BaseModel):
    """一次明确授权的 authoring 执行身份（方案 §5.1）。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["2.0"] = "2.0"
    execution_id: str
    parent_execution_id: str | None = None
    creation_mode: CreationMode = "new"

    engine_commit_sha: str
    engine_source_digest: str
    target_repo_snapshot_digest: str
    target_project_tree_hash: str
    target_source_manifest_digest: str = ""

    intent_content_digest: str
    claims_digest: str
    profile_digest: str
    #: 实际生效的配置（narrative mode / context mode / 输出协议 / prompt / tokenizer /
    #: 验收规则身份）——同一输入在不同模式下不得共享身份（审计 §A.1.6）。
    effective_config_digest: str = "unspecified"
    model_identity_digest: str
    prompt_bundle_digest: str
    tokenizer_contract_digest: str
    validator_bundle_digest: str
    research_import_digest: str | None = None

    #: 仅诊断用，不参与 content_digest：源码/目标搬到别的绝对路径、或同一内容换了
    #: commit 不应失去兼容性（审计 §A.1.3）。
    engine_root: str = ""
    target_git_commit: str = ""
    content_digest: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "AuthoringExecutionIdentityV2":
        for field_name in (
            "execution_id",
            "engine_commit_sha",
            "engine_source_digest",
            "target_repo_snapshot_digest",
            "target_project_tree_hash",
            "intent_content_digest",
            "claims_digest",
            "profile_digest",
            "effective_config_digest",
            "model_identity_digest",
            "prompt_bundle_digest",
            "tokenizer_contract_digest",
            "validator_bundle_digest",
        ):
            if not str(getattr(self, field_name) or "").strip():
                raise ValueError(f"execution identity requires {field_name}")
        expected = digest_json(self._payload())
        if self.content_digest and self.content_digest != expected:
            raise ValueError("execution identity content_digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self

    def _payload(self) -> dict[str, Any]:
        return self.model_dump(
            mode="json",
            exclude={
                "content_digest",
                "engine_root",
                "execution_id",
                "target_git_commit",
            },
        )

    def compatible_fields(self) -> dict[str, str]:
        """resume 比较使用的版本化兼容字段集合（不含 execution_id/content_digest）。"""

        return {
            key: str(value)
            for key, value in self._payload().items()
            if key not in {"schema_version"} and value is not None
        }

    @property
    def birth_metadata(self) -> BirthMetadataV1:
        """本次执行的出生信息（不可变来源），供 resume 继承。"""

        return BirthMetadataV1(
            creation_mode=self.creation_mode,
            parent_execution_id=self.parent_execution_id,
            research_import_digest=self.research_import_digest,
        )


def capture_validator_bundle_snapshot(
    engine_root: str | Path | None = None,
    *,
    sources: tuple[str, ...] | None = None,
) -> ValidatorBundleSnapshot:
    """指纹化验收规则来源；文件缺失/引擎根不可解析时如实记录失败码，不静默留空。"""

    root = Path(engine_root) if engine_root is not None else resolve_engine_root()
    relative_sources = tuple(sources if sources is not None else VALIDATOR_BUNDLE_SOURCES)
    if root is None:
        return ValidatorBundleSnapshot(
            digest=digest_json({"validator_bundle": "unavailable", "reason": "engine_root_unresolved"}),
            engine_root="",
            failure_code=ENGINE_ROOT_UNRESOLVED,
        )
    entries: list[tuple[str, str]] = []
    missing: list[str] = []
    unstable = False
    for relative in relative_sources:
        digest, was_unstable = _hash_file(root / relative)
        unstable = unstable or was_unstable
        if digest == "missing":
            missing.append(relative)
            continue
        entries.append((relative, digest))
    failure_code = ""
    if missing:
        failure_code = "validator_source_missing"
    if unstable:
        failure_code = "validator_source_unstable"
    payload = {
        "validator_bundle": "v1",
        "sources": dict(entries),
        "missing": sorted(missing),
        "failure_code": failure_code,
    }
    return ValidatorBundleSnapshot(
        digest=digest_json(payload),
        engine_root=str(root),
        entries=tuple(entries),
        missing=tuple(sorted(missing)),
        failure_code=failure_code,
    )


def build_execution_identity(
    *,
    target_repo_snapshot_digest: str,
    target_project_tree_hash: str,
    intent_content_digest: str,
    claims_digest: str,
    profile_digest: str,
    model_identity_digest: str,
    prompt_bundle_digest: str = "unspecified",
    tokenizer_contract_digest: str = "unspecified",
    validator_bundle_digest: str = "unspecified",
    engine_root: str | Path | None = None,
    engine_snapshot: EngineSourceSnapshot | None = None,
    target_source_manifest_digest: str = "",
    effective_config_digest: str = "unspecified",
    target_git_commit: str = "",
    creation_mode: CreationMode = "new",
    parent_execution_id: str | None = None,
    research_import_digest: str | None = None,
    require_usable_engine: bool = True,
) -> AuthoringExecutionIdentityV2:
    """构造执行身份；engine 指纹不可用时 fail-closed。"""

    snapshot = engine_snapshot or capture_engine_source_snapshot(engine_root)
    if require_usable_engine and not snapshot.is_usable:
        raise ValueError(
            f"engine_identity_unavailable:{snapshot.failure_code or 'engine_commit_unknown'}"
        )
    engine_commit = snapshot.commit_sha or "unknown"
    engine_source_digest = snapshot.source_digest or digest_json({
        "engine_source": "unavailable",
        "failure_code": snapshot.failure_code or "engine_commit_unknown",
    })
    payload = {
        "schema_version": "2.0",
        "parent_execution_id": parent_execution_id,
        "creation_mode": creation_mode,
        "engine_commit_sha": engine_commit,
        "engine_source_digest": engine_source_digest,
        "target_repo_snapshot_digest": str(target_repo_snapshot_digest),
        "target_project_tree_hash": str(target_project_tree_hash),
        "target_source_manifest_digest": str(target_source_manifest_digest or ""),
        "effective_config_digest": str(effective_config_digest or "unspecified"),
        "intent_content_digest": str(intent_content_digest),
        "claims_digest": str(claims_digest),
        "profile_digest": str(profile_digest),
        "model_identity_digest": str(model_identity_digest),
        "prompt_bundle_digest": str(prompt_bundle_digest),
        "tokenizer_contract_digest": str(tokenizer_contract_digest),
        "validator_bundle_digest": str(validator_bundle_digest),
        "research_import_digest": research_import_digest,
    }
    execution_id = "exec-" + digest_json(payload).split(":", 1)[-1][:16]
    return AuthoringExecutionIdentityV2(
        execution_id=execution_id,
        engine_root=snapshot.engine_root,
        target_git_commit=str(target_git_commit or ""),
        **payload,
    )


def _output_path(out_root: str | Path, key: str) -> Path:
    """按 out_root 直接拼接产物路径：不创建目录、不改写根目录推导。

    ``method_output`` 会按 ``artifacts`` 段重写根目录并顺手 mkdir，二者对
    "只读判断"和"拒绝时零写入"都是错的（事故目录本身就在 ``artifacts/`` 下）。
    """

    from code2paper.core.output_names import ALIASES, METHOD_OUTPUTS

    canonical = ALIASES.get(key, key)
    return Path(out_root) / METHOD_OUTPUTS[canonical]


def execution_identity_path(out_root: str | Path) -> Path:
    return _output_path(out_root, "authoring_execution_identity_v2")


def legacy_run_identity_path(out_root: str | Path) -> Path:
    return _output_path(out_root, "run_identity_v1")


def run_summary_path(out_root: str | Path) -> Path:
    return Path(out_root) / "artifacts" / "research_product" / "run_summary.json"


def load_execution_identity(
    out_root: str | Path,
) -> AuthoringExecutionIdentityV2 | None:
    path = execution_identity_path(out_root)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    try:
        return AuthoringExecutionIdentityV2.model_validate(payload)
    except ValueError:
        return None


class RunOpenDecision(BaseModel):
    """目录准入决策（方案 §5.3 的状态机输出）。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    allowed: bool
    code: str
    requested_mode: str
    effective_mode: str
    execution_id: str = ""
    identity_digest: str = ""
    mismatched_fields: tuple[str, ...] = ()
    exhausted_invocations: tuple[str, ...] = ()
    allowed_next_action: str = ""
    detail: str = ""

    def as_diagnostics(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def _is_launcher_owned(relative: str) -> bool:
    """启动器在"预检 → 加锁"之间自己写入的进程产物。

    这些文件不是 run 内容：进程日志、监督进程清单、attempt 记录与租约文件。
    目录准入忽略它们，才能既保持"new 拒绝非空目录"，又允许 CLI 先开日志。
    """

    normalized = relative.replace(os.sep, "/")
    name = normalized.rsplit("/", 1)[-1]
    if name == RUN_LEASE_FILE or name == "run_open_decision_v1.json":
        return True
    if name == "method_agent_process.json":
        return True
    if normalized.startswith("method_agent_attempts/"):
        return True
    if name.endswith(".log") and (
        name.startswith("run_stdout") or name.startswith("run_stderr")
    ):
        return True
    return False


def _directory_entries(out_root: Path) -> list[Path]:
    if not out_root.is_dir():
        return []
    entries: list[Path] = []
    for item in out_root.rglob("*"):
        if not item.is_file():
            continue
        relative = str(item.relative_to(out_root))
        if _is_launcher_owned(relative):
            continue
        entries.append(item)
    return entries


def scan_exhausted_invocations(
    out_root: str | Path,
    *,
    required_invocation_ids: Sequence[str] | None = None,
    content_attempt_limit: int | None = None,
) -> tuple[str, ...]:
    """只读扫描：哪些 invocation 已耗尽内容重试预算（审计 §B.4）。

    旧实现按"最新 completed 里有没有 attempt_limit_exhausted"判断，会漏判
    "两次真实失败但没有第三次拒发记录"，也会被历史拒发误导。现在这里是统一归约层
    :func:`writer_attempt_ledger.reduce_invocation_recovery` 的薄包装：
    只有状态为 ``content_budget_exhausted`` 的 invocation 才算耗尽。

    ``required_invocation_ids`` 给定时只汇总当前计划必需的调用，不受无关历史目录影响。
    """

    from code2paper.agentic.writer_attempt_ledger import (
        DEFAULT_CONTENT_ATTEMPT_LIMIT,
        reduce_invocation_recovery,
    )

    root = Path(out_root) / "artifacts" / "06_authoring" / "invocations"
    if not root.is_dir() and required_invocation_ids is None:
        return ()
    limit = int(content_attempt_limit or DEFAULT_CONTENT_ATTEMPT_LIMIT)

    if required_invocation_ids is not None:
        candidates: list[str] = [str(item) for item in required_invocation_ids if str(item)]
    else:
        candidates = []
        for directory in sorted(path for path in root.iterdir() if path.is_dir()):
            declared = ""
            for receipt in sorted(directory.glob("attempt-*.json")):
                try:
                    payload = json.loads(receipt.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if isinstance(payload, Mapping):
                    declared = str(payload.get("invocation_id") or "").strip()
                if declared:
                    break
            candidates.append(declared or directory.name)

    exhausted: set[str] = set()
    for invocation_id in candidates:
        recovery = reduce_invocation_recovery(
            out_root, invocation_id, content_attempt_limit=limit
        )
        if recovery.state == "content_budget_exhausted":
            exhausted.add(recovery.invocation_id)
    return tuple(sorted(exhausted))


def validate_run_open(
    out_root: str | Path,
    requested_mode: RunOpenMode | str,
    identity: AuthoringExecutionIdentityV2,
    *,
    exhausted_invocations: Sequence[str] | None = None,
    research_import_verifiable: bool = True,
) -> RunOpenDecision:
    """目录准入状态机（方案 §5.3）。任何拒绝都零模型调用、零写入。"""

    root = Path(out_root)
    mode = str(requested_mode or "auto").strip().casefold() or "auto"
    if mode not in {"auto", "new", "resume", "fork_authoring"}:
        raise ValueError(f"unknown run_open_mode:{mode}")

    existing_identity = load_execution_identity(root)
    legacy_present = legacy_run_identity_path(root).is_file()
    entries = _directory_entries(root)
    non_empty = bool(entries)
    exhausted = tuple(
        exhausted_invocations
        if exhausted_invocations is not None
        else scan_exhausted_invocations(root)
    )

    def decision(
        allowed: bool,
        code: str,
        *,
        effective: str,
        next_action: str = "",
        mismatched: Iterable[str] = (),
        detail: str = "",
    ) -> RunOpenDecision:
        return RunOpenDecision(
            allowed=allowed,
            code=code,
            requested_mode=mode,
            effective_mode=effective,
            execution_id=identity.execution_id,
            identity_digest=identity.content_digest,
            mismatched_fields=tuple(sorted(mismatched)),
            exhausted_invocations=exhausted,
            allowed_next_action=next_action,
            detail=detail,
        )

    if mode == "new":
        if non_empty:
            return decision(
                False,
                RUN_DIRECTORY_NOT_EMPTY,
                effective="new",
                next_action="use_resume_fork_or_empty_directory",
                detail=f"{len(entries)} existing file(s) under {root}",
            )
        return decision(True, "run_directory_empty", effective="new", next_action="run")

    if mode == "fork_authoring":
        if non_empty:
            return decision(
                False,
                RUN_DIRECTORY_NOT_EMPTY,
                effective="fork_authoring",
                next_action="use_empty_directory",
                detail=f"{len(entries)} existing file(s) under {root}",
            )
        if not research_import_verifiable:
            return decision(
                False,
                RESEARCH_IMPORT_UNVERIFIABLE,
                effective="fork_authoring",
                next_action="provide_verified_research_checkpoint",
            )
        return decision(
            True,
            "research_import_verified",
            effective="fork_authoring",
            next_action="run",
        )

    if mode == "resume":
        if (
            identity.engine_commit_sha in {"", "unknown"}
            or not identity.engine_source_digest
        ):
            return decision(
                False,
                RESUME_ENGINE_UNAVAILABLE,
                effective="resume",
                next_action="explicit_fork_authoring_or_restore_engine_fingerprint",
                detail="请求身份没有可用的引擎指纹，不能冒充严格 resume",
            )
        if existing_identity is None:
            return decision(
                False,
                RESUME_IDENTITY_LEGACY if legacy_present else RESUME_IDENTITY_MISSING,
                effective="resume",
                next_action=(
                    "explicit_fork_authoring"
                    if legacy_present
                    else "start_with_run_open_mode_new"
                ),
                detail=(
                    "legacy RunIdentityV1 缺少引擎指纹，不能冒充严格 resume"
                    if legacy_present
                    else "目录中没有 AuthoringExecutionIdentityV2"
                ),
            )
        current = existing_identity.compatible_fields()
        requested = identity.compatible_fields()
        mismatched = sorted(
            key
            for key in set(current) | set(requested)
            if current.get(key) != requested.get(key)
        )
        if mismatched:
            return decision(
                False,
                RESUME_IDENTITY_MISMATCH,
                effective="resume",
                next_action="fork_authoring_or_explicit_new",
                mismatched=mismatched,
            )
        if exhausted:
            return decision(
                False,
                RESUME_EXHAUSTED_INVOCATION,
                effective="resume",
                next_action="fork_authoring_with_new_contract",
                detail=f"{len(exhausted)} invocation(s) already exhausted",
            )
        return decision(
            True, "resume_identity_matched", effective="resume", next_action="resume"
        )

    # auto
    if existing_identity is not None:
        return validate_run_open(
            root,
            "resume",
            identity,
            exhausted_invocations=exhausted,
            research_import_verifiable=research_import_verifiable,
        ).model_copy(update={"requested_mode": mode})
    if non_empty:
        return decision(
            False,
            RUN_DIRECTORY_NOT_EMPTY,
            effective="auto",
            next_action="explicit_resume_fork_or_empty_directory",
            detail=(
                "目录非空且没有 AuthoringExecutionIdentityV2"
                + ("（仅存在 legacy RunIdentityV1）" if legacy_present else "")
            ),
        )
    return decision(True, "run_directory_empty", effective="new", next_action="run")


#: 取锁时身份尚未解析（身份要在锁内读既有目录才能定）时的占位 owner。
PENDING_LEASE_OWNER = "pending"


@dataclass(eq=False)
class RunLease:
    """单写者租约：持有 ``out_root`` 的排他 flock 直到释放或进程退出。

    语义：**跨进程互斥，进程内幂等**。同一进程对同一 ``out_root`` 重复获取
    返回同一个租约对象（该进程本来就是写者）；另一个进程会得到
    :class:`RunLeaseHeld`。
    """

    path: Path
    execution_id: str = PENDING_LEASE_OWNER
    key: str = ""
    _handle: Any = field(default=None, repr=False)

    def bind(self, execution_id: str) -> "RunLease":
        """把租约绑定到实际执行身份（锁内解析出身份后调用）。

        已绑定到另一个执行时拒绝：同一 out_root 上的两次不同执行不允许共享租约。
        """

        owner = str(execution_id or "").strip()
        if not owner:
            raise ValueError("run_lease_requires_execution_id")
        current = str(self.execution_id or "")
        if current not in {"", PENDING_LEASE_OWNER} and current != owner:
            raise RunLeaseHeld(
                f"{RUN_LEASE_HELD}:{self.path} (held_by={current} requested={owner})"
            )
        self.execution_id = owner
        if self._handle is not None:
            try:
                self._handle.seek(0)
                self._handle.truncate()
                self._handle.write(
                    json.dumps({"execution_id": owner, "pid": os.getpid()}) + "\n"
                )
                self._handle.flush()
            except OSError:
                pass
        return self

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            import fcntl

            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            self._handle.close()
        finally:
            self._handle = None
            if self.key:
                _HELD_LEASES.pop(self.key, None)

    def __enter__(self) -> "RunLease":
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()

    def __del__(self) -> None:  # pragma: no cover - 解释器退出路径
        try:
            self.release()
        except Exception:
            pass


class RunLeaseHeld(RuntimeError):
    """同一 run 目录已被另一个写者持有。"""

    code = RUN_LEASE_HELD


class RunOpenRejected(RuntimeError):
    """目录准入拒绝：零模型调用、零写入，附带结构化决策。"""

    def __init__(self, decision: RunOpenDecision) -> None:
        super().__init__(
            f"{decision.code}:{decision.detail or decision.allowed_next_action}"
        )
        self.decision = decision


@dataclass(frozen=True)
class TargetRepoIdentity:
    """目标（被研究）仓库的身份：**内容**身份 + 诊断字段（审计 §A.1）。

    旧实现把 target HEAD 塞进 ``target_repo_snapshot_digest``、把不含文件内容的
    porcelain 摘要塞进 ``target_project_tree_hash``——同一文件从实现 A 改成 B，
    HEAD 与路径状态都不变，身份就不变（审计 F02 最小反例）。

    现在复用既有 ``RepoSnapshot`` / source manifest 的文件选择规则得到真实内容摘要；
    ``commit_sha`` 与 ``dirty_digest`` 只作诊断，不参与"相同内容能否复用"的判断。
    """

    project_root: str
    commit_sha: str
    dirty_digest: str
    source_snapshot_digest: str = ""
    project_tree_hash: str = ""
    source_manifest_digest: str = ""
    file_count: int = 0
    failure_code: str = ""

    @property
    def is_usable(self) -> bool:
        return not self.failure_code and bool(self.source_snapshot_digest)

    def as_diagnostics(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "commit_sha": self.commit_sha,
            "source_snapshot_digest": self.source_snapshot_digest,
            "project_tree_hash": self.project_tree_hash,
            "source_manifest_digest": self.source_manifest_digest,
            "file_count": self.file_count,
            "failure_code": self.failure_code,
        }


def capture_target_identity(repo_path: str | Path) -> TargetRepoIdentity:
    """构建目标仓库的内容身份；不可用时如实给失败码，不伪造摘要。"""

    from code2paper.agentic.authoring_context_contract import dirty_manifest_digest

    root = Path(repo_path).expanduser()
    code, head = _run_git(root, "rev-parse", "HEAD")
    commit = head.strip() if code == 0 and head.strip() else "unknown"
    try:
        dirty = dirty_manifest_digest(root)
    except Exception:  # pragma: no cover - 非 git 目标仓库
        dirty = digest_json({"target_repo": "not-a-git-worktree"})

    failure_code = ""
    snapshot_digest = ""
    tree_hash = ""
    manifest_digest = ""
    file_count = 0
    if not root.is_dir():
        # 路径不存在/不可读：没有字节就没有内容身份（审计 §A.1.4）。
        return TargetRepoIdentity(
            project_root=str(root),
            commit_sha=commit,
            dirty_digest=dirty,
            failure_code=f"{TARGET_SNAPSHOT_UNAVAILABLE}:path_missing",
        )
    try:
        from code2paper.agentic.repo_snapshot import build_repo_snapshot
        from code2paper.agentic.source_inventory import build_repository_source_manifest

        snapshot = build_repo_snapshot(root)
        manifest = build_repository_source_manifest(snapshot)
        snapshot_digest = str(snapshot.content_digest)
        tree_hash = str(snapshot.project_tree_hash)
        manifest_digest = str(getattr(manifest, "content_digest", "") or "")
        file_count = len(snapshot.included_files)
        if not snapshot_digest or not tree_hash:
            failure_code = TARGET_SNAPSHOT_UNAVAILABLE
        if not manifest_digest:
            failure_code = failure_code or TARGET_SNAPSHOT_UNAVAILABLE
        if file_count == 0:
            # 空目录不是"内容相同"，而是没有可研究内容：不得给出可用身份。
            failure_code = failure_code or f"{TARGET_SNAPSHOT_UNAVAILABLE}:no_source_files"
    except Exception as exc:  # noqa: BLE001 - 身份不可用必须显式，不得静默
        failure_code = f"{TARGET_SNAPSHOT_UNAVAILABLE}:{type(exc).__name__}"

    return TargetRepoIdentity(
        project_root=str(root),
        commit_sha=commit,
        dirty_digest=dirty,
        source_snapshot_digest=snapshot_digest,
        project_tree_hash=tree_hash,
        source_manifest_digest=manifest_digest,
        file_count=file_count,
        failure_code=failure_code,
    )


def acquire_run_lease(
    out_root: str | Path,
    *,
    execution_id: str,
    blocking: bool = False,
) -> RunLease:
    """获取单写者租约。

    审计 §A.3：进程内"幂等复用"必须校验 owner 一致，而不是只看 root——否则同一进程里
    第二次、属于**另一个执行**的打开会静默复用别人的锁。``PENDING_LEASE_OWNER`` 只用于
    "先取锁、再在锁内解析身份"的调用序列（见 ``open_authoring_execution``）。
    """

    import fcntl

    root = Path(out_root).expanduser().resolve()
    key = str(root)
    requested_owner = str(execution_id or PENDING_LEASE_OWNER)
    existing = _HELD_LEASES.get(key)
    if existing is not None and existing._handle is not None:
        held_owner = str(existing.execution_id or "")
        if requested_owner == PENDING_LEASE_OWNER or held_owner == requested_owner:
            return existing
        raise RunLeaseHeld(
            f"{RUN_LEASE_HELD}:{root} (held_by={held_owner} requested={requested_owner})"
        )

    root.mkdir(parents=True, exist_ok=True)
    path = root / RUN_LEASE_FILE
    handle = path.open("a+", encoding="utf-8")
    flags = fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB
    try:
        fcntl.flock(handle.fileno(), flags)
    except OSError as exc:
        handle.close()
        raise RunLeaseHeld(
            f"{RUN_LEASE_HELD}:{root} (execution_id={execution_id})"
        ) from exc
    handle.seek(0)
    handle.truncate()
    handle.write(json.dumps({"execution_id": execution_id, "pid": os.getpid()}) + "\n")
    handle.flush()
    lease = RunLease(path=path, execution_id=execution_id, key=key, _handle=handle)
    _HELD_LEASES[key] = lease
    return lease


def verify_research_import(
    checkpoint_path: str | Path | None,
) -> tuple[bool, str, str]:
    """校验研究导入来源是否可信（方案 §5.3）。

    可信 = 文件存在、可解析、且带有目标仓库身份绑定（``repo_snapshot_id`` /
    ``project_tree_hash`` / ``run_id``）。只有文件名或空壳 JSON 一律拒绝。
    返回 ``(verifiable, content_digest, detail)``。
    """

    if checkpoint_path is None:
        return False, "", "no research checkpoint supplied"
    path = Path(checkpoint_path).expanduser()
    if not path.is_file():
        return False, "", f"research checkpoint missing: {path.name}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False, "", f"research checkpoint unreadable: {path.name}"
    if not isinstance(payload, dict):
        return False, "", "research checkpoint is not an object"
    binding = {
        key: str(payload.get(key) or "")
        for key in ("run_id", "repo_snapshot_id", "project_tree_hash")
    }
    missing = sorted(key for key, value in binding.items() if not value)
    if missing:
        return False, "", "research checkpoint lacks identity binding: " + ",".join(missing)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return True, "sha256:" + digest.hexdigest(), "checkpoint identity binding present"


def build_run_open_identity(
    *,
    repo_path: str | Path,
    author_intent_path: str | Path | None = None,
    claims_path: str | Path | None = None,
    llm_config: Any | None = None,
    run_open_mode: str = "auto",
    engine_snapshot: EngineSourceSnapshot | None = None,
    research_import_digest: str | None = None,
    validator_bundle: ValidatorBundleSnapshot | None = None,
    tokenizer_identity: str | None = None,
    narrative_plan_mode: Any | None = None,
    authoring_context_mode: Any | None = None,
    response_protocol: Any | None = None,
    environment: Mapping[str, str] | None = None,
    require_usable_inputs: bool = True,
    birth_metadata: BirthMetadataV1 | None = None,
    target_identity: TargetRepoIdentity | None = None,
) -> AuthoringExecutionIdentityV2:
    """从产品入口输入构造执行身份（预检与正式准入共用同一实现）。

    I10：``validator_bundle_digest`` 绑定**验收规则来源**（``VALIDATOR_BUNDLE_SOURCES``
    的逐文件内容指纹），因此改变验收语义的修改一定会改变执行身份，历史
    accepted/rejected 不会在同一个 receipt digest 名义下被重新解释。

    审计 §A.2：``birth_metadata`` 是"这次执行出生时是什么"。resume 必须由调用方
    （``resolve_open_identity``）从既有身份继承后传入，而不是由 ``run_open_mode``
    重新推导——后者会把合法的 fork 执行判成身份不匹配。
    """

    mode = str(run_open_mode or "auto").strip().casefold() or "auto"
    birth = birth_metadata or BirthMetadataV1(
        creation_mode="fork_authoring" if mode == "fork_authoring" else "new",
        research_import_digest=(str(research_import_digest or "") or None),
    )
    llm_payload: Mapping[str, Any] = (
        llm_config.model_dump(mode="json")
        if llm_config is not None and hasattr(llm_config, "model_dump")
        else {"llm_config": "absent" if llm_config is None else str(llm_config)}
    )
    engine = engine_snapshot or capture_engine_source_snapshot()
    target = target_identity or capture_target_identity(repo_path)
    bundle = validator_bundle or capture_validator_bundle_snapshot()
    tokenizer = str(tokenizer_identity or "").strip() or "unspecified"

    # 审计 §A.1.4/§A.1.5：引擎/目标/验收规则来源不可用时必须在**任何模型发送之前**停止，
    # 不能因为"失败状态也带一个 sha256 字符串"就当成可用身份。预检传
    # ``require_usable_inputs=False`` 以便把失败码作为阻断项如实报出，而不是抛穿。
    if require_usable_inputs:
        if not engine.is_usable:
            raise ValueError(
                f"{ENGINE_ROOT_UNRESOLVED if not engine.engine_root else ENGINE_SNAPSHOT_UNSTABLE}"
                f":{engine.failure_code or 'engine_commit_unknown'}"
            )
        if not target.is_usable:
            raise ValueError(f"{target.failure_code or TARGET_SNAPSHOT_UNAVAILABLE}")
        if not bundle.is_usable:
            raise ValueError(
                f"{VALIDATOR_BUNDLE_UNAVAILABLE}:{bundle.failure_code or 'unknown'}"
            )

    from code2paper.agentic.authoring_run_config import capture_effective_config_digest

    effective_config = capture_effective_config_digest(
        llm_config=llm_config,
        narrative_plan_mode=narrative_plan_mode,
        authoring_context_mode=authoring_context_mode,
        response_protocol=response_protocol,
        tokenizer_identity=tokenizer,
        validator_bundle_digest=bundle.digest,
        environment=environment,
    )
    return build_execution_identity(
        engine_snapshot=engine,
        target_repo_snapshot_digest=target.source_snapshot_digest or "unavailable",
        target_project_tree_hash=target.project_tree_hash or "unavailable",
        target_source_manifest_digest=target.source_manifest_digest,
        target_git_commit=target.commit_sha,
        intent_content_digest=_input_content_digest(author_intent_path),
        claims_digest=_input_content_digest(claims_path),
        profile_digest=digest_json(llm_payload),
        effective_config_digest=effective_config["digest"],
        model_identity_digest=digest_json({
            "provider": str(getattr(llm_config, "provider", "") or ""),
            "model": str(getattr(llm_config, "model", "") or ""),
        }),
        prompt_bundle_digest=digest_json({
            "role": str(getattr(llm_config, "role", "") or ""),
            "prompt_template_version": str(
                getattr(llm_config, "prompt_template_version", "") or ""
            ),
        }),
        tokenizer_contract_digest=digest_json({"tokenizer": tokenizer}),
        validator_bundle_digest=bundle.digest,
        require_usable_engine=require_usable_inputs,
        creation_mode=birth.creation_mode,
        parent_execution_id=birth.parent_execution_id,
        research_import_digest=birth.research_import_digest,
    )


#: fork 导入必须齐备的研究权威材料：(key, module, model)。缺失/无法校验/摘要不符
#: 都视为导入不完整——"checkpoint 外壳正确"不等于证据可用（审计 §A.4）。
RESEARCH_IMPORT_REQUIRED_ARTIFACTS: tuple[tuple[str, str, str], ...] = (
    ("intent_graph", "code2paper.agentic.intent_compiler_v2", "IntentObligationGraphV2"),
    ("agenda", "code2paper.agentic.research_models", "ResearchAgendaV1"),
    ("atomic_claims", "code2paper.agentic.evidence_compiler_v3", "AtomicClaimSetV3"),
    ("evidence_packets", "code2paper.agentic.evidence_compiler_v3", "EvidencePacketSetV3"),
    ("code_facts", "code2paper.agentic.evidence_compiler_v3", "CodeFactSetV1"),
    ("source_manifest", "code2paper.agentic.source_inventory", "RepositorySourceManifestV1"),
    ("symbol_index", "code2paper.agentic.behavior_graph", "SymbolIndexV2"),
    ("implementation_scope", "code2paper.agentic.implementation_scope", "ImplementationScopeV1"),
)

#: fork 默认**不得**继承的 payload 前缀：写作尝试、内容验收、Binder/Realizer 回执、
#: 已发布 candidate、旧调用预算、活动指针与租约。
RESEARCH_IMPORT_FORBIDDEN_PREFIXES: tuple[str, ...] = (
    "writer_",
    "writer",
    "content_acceptance",
    "binder_receipt",
    "realizer_receipt",
    "publication_candidate",
    "repository_verified_method",
    "invocation_budget",
    "run_budget",
    "active_pointer",
    "run_lease",
)


class ResearchImportClosureV1(BaseModel):
    """研究导入的闭包校验结果（审计 §A.4）。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    verifiable: bool = False
    digest: str = ""
    detail: str = ""
    codes: tuple[str, ...] = ()
    validated_artifacts: tuple[str, ...] = ()
    forbidden_payload_keys: tuple[str, ...] = ()
    path_violations: tuple[str, ...] = ()
    project_tree_hash: str = ""
    repo_snapshot_id: str = ""


def _unsafe_relative_path(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    if text.startswith("/") or text.startswith("\\") or ":" in text.split("/")[0]:
        return True
    normalized = text.replace("\\", "/")
    return any(part in {"..", "~"} for part in normalized.split("/"))


def verify_research_import_closure(
    checkpoint_path: str | Path | None,
    *,
    expected_project_tree_hash: str | None = None,
) -> ResearchImportClosureV1:
    """校验研究导入的可用性、路径安全与内容一致性，并拒绝写作/发布类继承。"""

    verifiable, digest, detail = verify_research_import(checkpoint_path)
    if not verifiable:
        return ResearchImportClosureV1(
            verifiable=False, digest=digest, detail=detail, codes=(RESEARCH_IMPORT_UNVERIFIABLE,)
        )
    path = Path(checkpoint_path).expanduser()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ResearchImportClosureV1(
            verifiable=False,
            digest=digest,
            detail="research checkpoint unreadable",
            codes=(RESEARCH_IMPORT_UNVERIFIABLE,),
        )
    if not isinstance(payload, Mapping):
        return ResearchImportClosureV1(
            verifiable=False,
            digest=digest,
            detail="research checkpoint is not an object",
            codes=(RESEARCH_IMPORT_UNVERIFIABLE,),
        )

    codes: list[str] = []
    validated: list[str] = []
    project_tree_hash = str(payload.get("project_tree_hash") or "")
    repo_snapshot_id = str(payload.get("repo_snapshot_id") or "")

    # 1) provenance：导入必须属于当前目标仓库（同内容同 tree hash）。
    if expected_project_tree_hash and project_tree_hash != expected_project_tree_hash:
        codes.append("research_import_target_mismatch")

    # 2) required authority artifacts：存在 + 可用模型校验 + 内联摘要自洽。
    import importlib

    artifacts: dict[str, Mapping[str, Any]] = {}
    for key, module_name, class_name in RESEARCH_IMPORT_REQUIRED_ARTIFACTS:
        artifact = payload.get(key)
        if not isinstance(artifact, Mapping) or not artifact:
            codes.append(f"research_import_artifact_missing:{key}")
            continue
        model = getattr(importlib.import_module(module_name), class_name)
        try:
            instance = model.model_validate(dict(artifact))
        except Exception as exc:  # noqa: BLE001 - 导入校验必须报告而不是抛穿
            codes.append(f"research_import_artifact_invalid:{key}:{type(exc).__name__}")
            continue
        recorded = str(artifact.get("content_digest") or "")
        # 会自封摘要的模型：删掉 digest 重新校验，若模型能算出摘要就必须与原值一致
        # （篡改内容会导致不一致）。要求显式 digest 的模型无法重算，由下面的
        # identity/链一致性检查兜住。
        rebuilt = {k: v for k, v in artifact.items() if k != "content_digest"}
        try:
            resealed = str(getattr(model.model_validate(rebuilt), "content_digest", "") or "")
        except Exception:  # noqa: BLE001 - 该模型要求显式 digest，跳过重算
            resealed = ""
        if recorded and resealed and resealed != recorded:
            codes.append(f"research_import_artifact_digest_mismatch:{key}")
            continue
        # 声明了目标身份的产物必须与 checkpoint 顶层一致。
        declared_tree = str(artifact.get("project_tree_hash") or "")
        declared_snapshot = str(artifact.get("repo_snapshot_id") or "")
        if declared_tree and project_tree_hash and declared_tree != project_tree_hash:
            codes.append(f"research_import_identity_inconsistent:{key}")
            continue
        if declared_snapshot and repo_snapshot_id and declared_snapshot != repo_snapshot_id:
            codes.append(f"research_import_identity_inconsistent:{key}")
            continue
        artifacts[key] = artifact
        validated.append(key)

    # digest 链闭合：facts → packets → claims 之间的引用必须互相指对。
    packets_digest = str((artifacts.get("evidence_packets") or {}).get("content_digest") or "")
    facts_digest = str((artifacts.get("code_facts") or {}).get("content_digest") or "")
    chain = (
        ("code_facts", "evidence_packet_digest", packets_digest),
        ("atomic_claims", "evidence_packet_digest", packets_digest),
        ("atomic_claims", "code_fact_digest", facts_digest),
    )
    for key, field, expected in chain:
        artifact = artifacts.get(key)
        if artifact is None or not expected:
            continue
        declared = str(artifact.get(field) or "")
        if declared and declared != expected:
            codes.append(f"research_import_digest_chain_broken:{key}.{field}")

    # 3) path safety：manifest/symbol index 里声明的仓库内路径必须相对且无穿越。
    violations: list[str] = []
    manifest = payload.get("source_manifest")
    if isinstance(manifest, Mapping):
        for entry in manifest.get("entries") or ():
            if isinstance(entry, Mapping):
                candidate = str(entry.get("path") or "")
                if _unsafe_relative_path(candidate):
                    violations.append(candidate)
    symbol_index = payload.get("symbol_index")
    if isinstance(symbol_index, Mapping):
        for entry in symbol_index.get("entries") or ():
            if isinstance(entry, Mapping):
                candidate = str(entry.get("path") or "")
                if _unsafe_relative_path(candidate):
                    violations.append(candidate)
    if violations:
        codes.append("research_import_unsafe_path")

    # 4) 不得继承写作/验收/发布/预算/活动指针 payload。
    forbidden = tuple(
        sorted(
            str(key)
            for key in payload
            if any(str(key).startswith(prefix) for prefix in RESEARCH_IMPORT_FORBIDDEN_PREFIXES)
        )
    )
    if forbidden:
        codes.append("research_import_forbidden_payload")

    return ResearchImportClosureV1(
        verifiable=not codes,
        digest=digest,
        detail=(
            "研究导入闭包校验通过"
            if not codes
            else "研究导入闭包校验失败：" + ",".join(dict.fromkeys(codes))
        ),
        codes=tuple(dict.fromkeys(codes)),
        validated_artifacts=tuple(validated),
        forbidden_payload_keys=forbidden,
        path_violations=tuple(dict.fromkeys(violations))[:8],
        project_tree_hash=project_tree_hash,
        repo_snapshot_id=repo_snapshot_id,
    )


def research_import_parent_execution_id(checkpoint_path: str | Path | None) -> str | None:
    """研究导入里若记录了来源执行 id，则用它作为 ``parent_execution_id``（可选）。"""

    if checkpoint_path is None:
        return None
    path = Path(checkpoint_path).expanduser()
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, Mapping):
        return None
    for key in ("parent_execution_id", "execution_id"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return None


def resolve_open_identity(
    out_root: str | Path,
    *,
    run_open_mode: str,
    repo_path: str | Path,
    author_intent_path: str | Path | None = None,
    claims_path: str | Path | None = None,
    llm_config: Any | None = None,
    research_stage_checkpoint: str | Path | None = None,
    research_import_digest: str | None = None,
    require_usable_inputs: bool = True,
    **identity_options: Any,
) -> tuple[AuthoringExecutionIdentityV2, bool, str]:
    """按"本次打开动作"解析执行身份（审计 §A.2）。

    返回 ``(identity, research_import_verifiable, detail)``：

    * ``resume`` / ``auto`` 且目录里已有完整身份 → **继承其出生信息**
      （creation_mode / parent / import），不重新发明；
    * 其它情况 → 按本次动作构造新的出生信息；``fork_authoring`` 必须提供可校验的
      研究导入；
    * 旧版本没有完整身份时不"猜"：继承失败后仍由 :func:`validate_run_open`
      以 ``resume_identity_missing`` / ``resume_identity_legacy_incompatible`` 拒绝。
    """

    mode = str(run_open_mode or "auto").strip().casefold() or "auto"
    if mode not in {"auto", "new", "resume", "fork_authoring"}:
        raise ValueError(f"unknown run_open_mode:{mode}")

    existing = load_execution_identity(out_root)
    verifiable, import_digest, detail = (True, "", "")
    target_identity: TargetRepoIdentity | None = None
    if mode == "fork_authoring":
        # 审计 §A.4：不只看 checkpoint 外壳，还要校验内联证据可验证、摘要自洽、
        # 路径安全、且导入不属于当前目标仓库时拒绝。
        target_identity = capture_target_identity(repo_path)
        closure = verify_research_import_closure(
            research_stage_checkpoint,
            expected_project_tree_hash=target_identity.project_tree_hash or None,
        )
        verifiable, import_digest, detail = (
            closure.verifiable,
            closure.digest,
            closure.detail,
        )
        if not closure.verifiable:
            raise RunOpenRejected(
                RunOpenDecision(
                    allowed=False,
                    code=closure.codes[0] if closure.codes else RESEARCH_IMPORT_UNVERIFIABLE,
                    requested_mode=mode,
                    effective_mode=mode,
                    allowed_next_action="provide_a_verified_research_checkpoint_for_this_target",
                    detail=closure.detail[:320],
                )
            )
    elif research_import_digest:
        import_digest = str(research_import_digest)

    if mode in {"resume", "auto"} and existing is not None:
        birth = existing.birth_metadata
        detail = detail or "出生信息继承自既有身份"
        if research_stage_checkpoint is not None:
            # 续跑不该重新导入；但调用方**显式提供**了 checkpoint 时不能静默忽略：
            # 内容不同意味着操作者以为在跑另一份证据 → 必须拒绝（审计 §A.5）。
            supplied_ok, supplied_digest, supplied_detail = verify_research_import(
                research_stage_checkpoint
            )
            if not supplied_ok:
                raise RunOpenRejected(
                    RunOpenDecision(
                        allowed=False,
                        code=RESEARCH_IMPORT_UNVERIFIABLE,
                        requested_mode=mode,
                        effective_mode=mode,
                        allowed_next_action="provide_verified_research_checkpoint",
                        detail=str(supplied_detail)[:320],
                    )
                )
            if (
                birth.research_import_digest
                and supplied_digest != birth.research_import_digest
            ):
                raise RunOpenRejected(
                    RunOpenDecision(
                        allowed=False,
                        code="research_import_digest_mismatch",
                        requested_mode=mode,
                        effective_mode=mode,
                        allowed_next_action="fork_authoring_with_the_new_research_import",
                        detail="续跑提供的 checkpoint 与既有身份的出生导入不一致",
                    )
                )
    else:
        birth = BirthMetadataV1(
            creation_mode="fork_authoring" if mode == "fork_authoring" else "new",
            parent_execution_id=(
                research_import_parent_execution_id(research_stage_checkpoint)
                if mode == "fork_authoring"
                else None
            ),
            research_import_digest=(import_digest or None),
        )
    identity = build_run_open_identity(
        repo_path=repo_path,
        author_intent_path=author_intent_path,
        claims_path=claims_path,
        llm_config=llm_config,
        run_open_mode=mode,
        research_import_digest=import_digest,
        birth_metadata=birth,
        require_usable_inputs=require_usable_inputs,
        target_identity=target_identity,
        **identity_options,
    )
    return identity, verifiable, detail


def preflight_run_open(
    out_root: str | Path,
    requested_mode: RunOpenMode | str,
    *,
    repo_path: str | Path,
    author_intent_path: str | Path | None = None,
    claims_path: str | Path | None = None,
    llm_config: Any | None = None,
    research_import_path: str | Path | None = None,
    **identity_options: Any,
) -> RunOpenDecision:
    """只读预检：在启动器写入任何进程产物之前给出准入决策。"""

    mode = str(requested_mode or "auto")
    try:
        identity, verifiable, _detail = resolve_open_identity(
            out_root,
            run_open_mode=mode,
            repo_path=repo_path,
            author_intent_path=author_intent_path,
            claims_path=claims_path,
            llm_config=llm_config,
            research_stage_checkpoint=research_import_path,
            # 只读预检也必须 fail-closed：输入不可用就拒绝（live 准入报告走
            # preflight_live_admission 的 require_usable_inputs=False 分支）。
            require_usable_inputs=True,
            **identity_options,
        )
    except RunOpenRejected as rejected:
        return rejected.decision
    except ValueError as exc:
        # 身份输入不可用（引擎/目标/验收规则来源）→ 类型化拒绝，不抛穿给调用方。
        return RunOpenDecision(
            allowed=False,
            code=str(exc).split(":", 1)[0] or "run_open_identity_unavailable",
            requested_mode=mode,
            effective_mode=mode,
            allowed_next_action="repair_engine_target_or_validator_inputs",
            detail=str(exc)[:320],
        )
    return validate_run_open(
        out_root,
        mode,
        identity,
        research_import_verifiable=verifiable,
    )


def _input_content_digest(path: str | Path | None) -> str:
    """输入文件的字节级身份；缺失是显式事实，不用空串冒充。"""

    if path is None:
        return digest_json({"input": "absent"})
    candidate = Path(path).expanduser()
    if not candidate.is_file():
        return digest_json({"input": "absent", "name": candidate.name})
    digest = hashlib.sha256()
    with candidate.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _identity_publication_failures(payload: Any) -> tuple[str, ...]:
    """发布前严格验证：身份必须能被同一模型读回（审计 §F.4 的验证步）。"""

    try:
        AuthoringExecutionIdentityV2.model_validate(payload)
    except ValueError as exc:
        return (f"authoring_execution_identity_invalid:{type(exc).__name__}",)
    return ()


def create_or_validate_execution_identity(
    out_root: str | Path,
    identity: AuthoringExecutionIdentityV2,
) -> tuple[str, str]:
    """写入或校验身份；已存在且不一致时 fail-closed（不改写旧身份）。"""

    path = execution_identity_path(out_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        existing = load_execution_identity(out_root)
        if existing is None:
            raise ValueError(f"{RESUME_IDENTITY_MISMATCH}:unreadable:{path}")
        if existing.content_digest != identity.content_digest:
            current = existing.compatible_fields()
            requested = identity.compatible_fields()
            mismatched = sorted(
                key
                for key in set(current) | set(requested)
                if current.get(key) != requested.get(key)
            )
            raise ValueError(
                f"{RESUME_IDENTITY_MISMATCH}:" + ",".join(mismatched or ["content_digest"])
            )
        return str(path), "validated"
    # 审计 §F.4：按"临时文件 → 严格验证 → 原子发布 → 注册 → 指针"的事务顺序发布，
    # 每一步进 journal；中断只会留下 incomplete/orphan，active 不会指向半成品。
    from code2paper.agentic.authoring_artifact_publication import (
        publish_artifact_transaction,
    )

    transaction = publish_artifact_transaction(
        out_root,
        role="authoring_execution_identity",
        phase="research",
        target_path=path,
        payload=(identity.model_dump_json(indent=2) + "\n").encode("utf-8"),
        generation=1,
        producer="authoring_execution_identity.create_or_validate_execution_identity",
        upstream_refs=(
            f"engine:{identity.engine_source_digest}",
            f"target:{identity.target_repo_snapshot_digest}",
            f"intent:{identity.intent_content_digest}",
            f"profile:{identity.profile_digest}",
            f"effective_config:{identity.effective_config_digest}",
            f"validator_bundle:{identity.validator_bundle_digest}",
        ),
        validator=_identity_publication_failures,
    )
    if transaction.state != "complete":
        raise ValueError(
            "authoring_execution_identity_publish_incomplete:"
            + ",".join(transaction.failures or (transaction.state,))
        )
    return str(path), "created"


__all__ = [
    "AuthoringExecutionIdentityV2",
    "CreationMode",
    "EngineDirtyEntry",
    "EngineSourceSnapshot",
    "RunLease",
    "RunLeaseHeld",
    "RunOpenDecision",
    "RunOpenMode",
    "RunOpenRejected",
    "TargetRepoIdentity",
    "acquire_run_lease",
    "build_execution_identity",
    "build_run_open_identity",
    "capture_engine_source_snapshot",
    "capture_target_identity",
    "preflight_run_open",
    "create_or_validate_execution_identity",
    "execution_identity_path",
    "legacy_run_identity_path",
    "load_execution_identity",
    "resolve_engine_root",
    "run_summary_path",
    "scan_exhausted_invocations",
    "validate_run_open",
    "verify_research_import",
    "ENGINE_ROOT_UNRESOLVED",
    "ENGINE_SNAPSHOT_UNSTABLE",
    "RESEARCH_IMPORT_UNVERIFIABLE",
    "RESUME_EXHAUSTED_INVOCATION",
    "RESUME_IDENTITY_LEGACY",
    "RESUME_IDENTITY_MISMATCH",
    "RESUME_IDENTITY_MISSING",
    "RESUME_ENGINE_UNAVAILABLE",
    "RUN_DIRECTORY_NOT_EMPTY",
    "TARGET_SNAPSHOT_UNAVAILABLE",
    "VALIDATOR_BUNDLE_UNAVAILABLE",
    "VALIDATOR_BUNDLE_SOURCES",
    "ValidatorBundleSnapshot",
    "capture_validator_bundle_snapshot",
    "RUN_LEASE_FILE",
    "RUN_LEASE_HELD",
]
