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
from code2paper.agentic.tool_runtime import atomic_write_bytes


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
    model_identity_digest: str
    prompt_bundle_digest: str
    tokenizer_contract_digest: str
    validator_bundle_digest: str
    research_import_digest: str | None = None

    #: 仅诊断用，不参与 content_digest：源码搬到别的绝对路径不应失去兼容性。
    engine_root: str = ""
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
            mode="json", exclude={"content_digest", "engine_root", "execution_id"}
        )

    def compatible_fields(self) -> dict[str, str]:
        """resume 比较使用的版本化兼容字段集合（不含 execution_id/content_digest）。"""

        return {
            key: str(value)
            for key, value in self._payload().items()
            if key not in {"schema_version"} and value is not None
        }


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


def scan_exhausted_invocations(out_root: str | Path) -> tuple[str, ...]:
    """只读扫描：哪些 invocation 已在历史记录中耗尽内容重试预算。

    判据取自持久回执本身：最新一条 ``*.completed.json`` 的
    ``delivery_rejection_code`` 以 ``attempt_limit_exhausted:`` 开头。
    这使"恢复一个已经烧掉预算的 run"可以被显式阻断，而不是再写一条
    attempt-0005 之后才在末尾报 acceptance_count:0（事故 §1.1、§9.3）。
    """

    root = Path(out_root) / "artifacts" / "06_authoring" / "invocations"
    if not root.is_dir():
        return ()
    exhausted: set[str] = set()
    for directory in sorted(root.iterdir()):
        if not directory.is_dir():
            continue
        latest: tuple[float, str] | None = None
        for record in directory.glob("*.completed.json"):
            try:
                payload = json.loads(record.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            invocation_id = str(payload.get("invocation_id") or "")
            code = str(payload.get("delivery_rejection_code") or "")
            if not invocation_id or not code.startswith("attempt_limit_exhausted:"):
                continue
            stamp = record.stat().st_mtime
            if latest is None or stamp >= latest[0]:
                latest = (stamp, invocation_id)
        if latest is not None:
            exhausted.add(latest[1])
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


@dataclass(eq=False)
class RunLease:
    """单写者租约：持有 ``out_root`` 的排他 flock 直到释放或进程退出。

    语义：**跨进程互斥，进程内幂等**。同一进程对同一 ``out_root`` 重复获取
    返回同一个租约对象（该进程本来就是写者）；另一个进程会得到
    :class:`RunLeaseHeld`。
    """

    path: Path
    execution_id: str
    key: str = ""
    _handle: Any = field(default=None, repr=False)

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
    """目标（被研究）仓库的准入代理身份。

    完整 ``RepoSnapshot`` 由研究 runtime 稍后才计算；目录准入必须先于它完成，
    因此这里用目标仓库的 commit + dirty 摘要作为准入代理，并在 runtime 建立后
    复查 commit 是否一致。
    """

    project_root: str
    commit_sha: str
    dirty_digest: str


def capture_target_identity(repo_path: str | Path) -> TargetRepoIdentity:
    from code2paper.agentic.authoring_context_contract import dirty_manifest_digest

    root = Path(repo_path).expanduser()
    code, head = _run_git(root, "rev-parse", "HEAD")
    commit = head.strip() if code == 0 and head.strip() else "unknown"
    try:
        dirty = dirty_manifest_digest(root)
    except Exception:  # pragma: no cover - 非 git 目标仓库
        dirty = digest_json({"target_repo": "not-a-git-worktree"})
    return TargetRepoIdentity(
        project_root=str(root), commit_sha=commit, dirty_digest=dirty
    )


def acquire_run_lease(
    out_root: str | Path,
    *,
    execution_id: str,
    blocking: bool = False,
) -> RunLease:
    import fcntl

    root = Path(out_root).expanduser().resolve()
    key = str(root)
    existing = _HELD_LEASES.get(key)
    if existing is not None and existing._handle is not None:
        return existing

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
) -> AuthoringExecutionIdentityV2:
    """从产品入口输入构造执行身份（预检与正式准入共用同一实现）。

    I10：``validator_bundle_digest`` 绑定**验收规则来源**（``VALIDATOR_BUNDLE_SOURCES``
    的逐文件内容指纹），因此改变验收语义的修改一定会改变执行身份，历史
    accepted/rejected 不会在同一个 receipt digest 名义下被重新解释。
    """

    is_fork = str(run_open_mode or "").strip().casefold() == "fork_authoring"
    llm_payload: Mapping[str, Any] = (
        llm_config.model_dump(mode="json")
        if llm_config is not None and hasattr(llm_config, "model_dump")
        else {"llm_config": "absent" if llm_config is None else str(llm_config)}
    )
    target = capture_target_identity(repo_path)
    return build_execution_identity(
        engine_snapshot=engine_snapshot or capture_engine_source_snapshot(),
        target_repo_snapshot_digest=target.commit_sha,
        target_project_tree_hash=target.dirty_digest,
        intent_content_digest=_input_content_digest(author_intent_path),
        claims_digest=_input_content_digest(claims_path),
        profile_digest=digest_json(llm_payload),
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
        tokenizer_contract_digest=digest_json({
            "tokenizer": str(tokenizer_identity or "").strip() or "unspecified"
        }),
        validator_bundle_digest=(
            validator_bundle or capture_validator_bundle_snapshot()
        ).digest,
        creation_mode="fork_authoring" if is_fork else "new",
        research_import_digest=(str(research_import_digest or "") or None),
        # 引擎指纹不可用时允许"新执行"继续（并如实记录 unknown），
        # 但 validate_run_open 会拒绝把它当作严格 resume（方案 §5.2）。
        require_usable_engine=False,
    )


def preflight_run_open(
    out_root: str | Path,
    requested_mode: RunOpenMode | str,
    *,
    repo_path: str | Path,
    author_intent_path: str | Path | None = None,
    claims_path: str | Path | None = None,
    llm_config: Any | None = None,
    research_import_path: str | Path | None = None,
) -> RunOpenDecision:
    """只读预检：在启动器写入任何进程产物之前给出准入决策。"""

    mode = str(requested_mode or "auto")
    verifiable, import_digest, _detail = (True, "", "")
    if mode.strip().casefold() == "fork_authoring":
        verifiable, import_digest, _detail = verify_research_import(research_import_path)
    identity = build_run_open_identity(
        repo_path=repo_path,
        author_intent_path=author_intent_path,
        claims_path=claims_path,
        llm_config=llm_config,
        run_open_mode=mode,
        research_import_digest=import_digest,
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
    atomic_write_bytes(
        path,
        (identity.model_dump_json(indent=2) + "\n").encode("utf-8"),
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
    "VALIDATOR_BUNDLE_SOURCES",
    "ValidatorBundleSnapshot",
    "capture_validator_bundle_snapshot",
    "RUN_LEASE_FILE",
    "RUN_LEASE_HELD",
]
