"""冻结的 2026-09-17 EBCAR intent-v4 P7 authoring 事故归档定位器。

本模块实现 `docs/code2paper_repair_execution_20260917.md` 的 WP0（§4）：事故事实
必须可重复解释，且不得依赖宿主 `/tmp` 或重新解释历史。

做法：
* 事故事实直接从仓库内已提交的归档目录读取，不复制、不改写；
* 每个条目同时固定两个身份——归档提交中的 **Git blob SHA** 与文件字节的
  **sha256**。任一不符即 `IncidentArchiveDrift`，即"为新规则改答案"会在
  冻结 oracle 处失败（方案 §12.2）。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

ARCHIVE_RELATIVE_ROOT = Path("artifacts/runs/2026-09-17-ebcar-intent-v4-p7-j9L1bn")

INCIDENT_INVOCATION = (
    "inv:writer:MA-S3:page:"
    "751aa8b5352377a0766e7f7416c05553647380df74d5295f04d695646a47b815"
)
INCIDENT_PAGE_ID = (
    "page:751aa8b5352377a0766e7f7416c05553647380df74d5295f04d695646a47b815"
)
INCIDENT_INVOCATION_DIR = (
    "artifacts/06_authoring/invocations/"
    "inv-writer-MA-S3-page-"
    "751aa8b5352377a0766e7f7416c05553647380df74d5295f04d695646a47b815-"
    "f463066ebdc243a6"
)

TARGET_REPO_COMMIT = "287506e3e2df30e3c840b8f6398b5010c25111e1"
TARGET_REPO_ROOT = (
    "/data1/users/cuihengjia/code2paper/code_final/"
    "EBCAR - Embedding-Based Context-Aware Reranker"
)

#: attempt-0002 缺失的两个实现细节 witness（canonical target id，未加显示前缀）。
INCIDENT_MISSING_DETAIL_TARGETS = (
    "mech_sym:f6cf5bdfe2ae16f0:15",
    "mech_sym:f6cf5bdfe2ae16f0:76",
)
#: MA-S3 页在 Writer 请求中的 16 个段落，P3 起为无独立材料槽位。
INCIDENT_PAGE_PARAGRAPH_IDS = (
    "MA-S3:P1__f1",
    *(f"MA-S3:P{n}" for n in range(3, 18)),
)
INCIDENT_EMPTY_SLOT_IDS = tuple(f"MA-S3:P{n}" for n in range(3, 18))


class IncidentArchiveDrift(AssertionError):
    """归档内容与固定身份不一致：冻结 oracle 被改动。"""


@dataclass(frozen=True)
class PinnedArtifact:
    key: str
    path: str
    git_blob_sha: str
    sha256: str
    purpose: str


_PINNED: tuple[PinnedArtifact, ...] = (
    PinnedArtifact(
        "run_identity",
        "artifacts/research_product/run_identity_v1.json",
        "97ea90a58a9b48aab80f5de5ab3e2f3d1bc68135",
        "sha256:aec2ca159413a4766f1b4ad493dc9d46274cb3bd9a51ea530985a909cf464d4f",
        "RunIdentityV1：证明 code_commit_sha 取自目标 RepoSnapshot，引擎身份缺失",
    ),
    PinnedArtifact(
        "repo_snapshot",
        "artifacts/repo_snapshot_v2.json",
        "5dc686fbf60615d5a3167d347394b262c6b25d19",
        "sha256:abf107ba319e13a73bd8a541f15f5b7defea18e98175507007c5e98145aaab9e",
        "目标仓库 EBCAR 快照：git_commit 与 project_root 归属",
    ),
    PinnedArtifact(
        "run_summary",
        "artifacts/research_product/run_summary.json",
        "0347544f35207c12d9e14602ec8f308d34820062",
        "sha256:603bc225d6c85f246d500310e634cb17e62068627040d95b03ae0c7e6b91fae2",
        "运行终态摘要（writer blocked 原因链）",
    ),
    PinnedArtifact(
        "writer_section_receipts",
        "artifacts/06_authoring/writer_section_receipts_v2.json",
        "50bf4882d734e55cbabaad35469214f0572ff9a2",
        "sha256:3826f09767fcaa5336f48a44bf7825b13ae84e6df260b219b282af2543fa9acb",
        "分节 Writer 回执：MA-S3 为 15/16",
    ),
    PinnedArtifact(
        "writer_aggregate_receipt",
        "artifacts/06_authoring/writer_aggregate_receipt_v2.json",
        "0cebc1cf947b8d0d3653b855e79b9c3d3c14f039",
        "sha256:9506401e391485fc91e5c98f4e13316777c07e21063aef447d788cfec7aa4cba",
        "聚合回执：all_required_sections_complete=false",
    ),
    PinnedArtifact(
        "writer_result",
        "artifacts/06_authoring/publication_writer_result_v1.json",
        "cf6d2258d63dee5bddd1ff295b2f4a8efa321341",
        "sha256:7231f8f6b215e41bdf6a0de417238ee305232bcf9c4efce7caf814b63275f460",
        "Writer 阶段结果：blocked 与 candidate 未写出",
    ),
    PinnedArtifact(
        "formalizer_workset_manifest",
        "artifacts/06_authoring/consumer_workset_manifest_v2.json",
        "6a6ab478c5820951da3d48606e159b9374e99c57",
        "sha256:25ea48ea46bfb8926c8ed99ec956ed813dcad5d89a15389d57608dbf5f554df4",
        "Formalizer 阶段基础 manifest：合法空产物",
    ),
    PinnedArtifact(
        "writer_workset_manifest",
        "artifacts/06_authoring/consumer_workset_manifest_v2.writer.2.json",
        "969351e7fbe7d1ef30a9faba24fc6b6a7011712f",
        "sha256:9bbc5da7e4b3286b4e7902e85d04c7cdab9895f10ea5deb35d41bf3521698cf7",
        "Writer 阶段 phase-specific manifest：5 worksets / 20 pages",
    ),
    PinnedArtifact(
        "attempt_0001_request",
        f"{INCIDENT_INVOCATION_DIR}/attempt-0001.provider-request.json",
        "801cb40230dbeac24974d73474fe842b3debe3fc",
        "sha256:03a5155cba74cabc66d6a798cc36988c3b796bf04820059d2efab7f15c4b19e3",
        "第 1 次实际请求：16 段页契约",
    ),
    PinnedArtifact(
        "attempt_0001_acceptance",
        f"{INCIDENT_INVOCATION_DIR}/attempt-0001.content-acceptance.json",
        "8ba956b7081b61127a8c97861a374c00eedde6a6",
        "sha256:5d910e521a3bc68f188fe90a14135c6c68c619023db71318b921cb7c6196d0bb",
        "第 1 次内容验收：15 段 missing_paragraph",
    ),
    PinnedArtifact(
        "attempt_0002_request",
        f"{INCIDENT_INVOCATION_DIR}/attempt-0002.provider-request.json",
        "f255dcecba1bc7be428af5b01629cdb7f394e324",
        "sha256:e7b1143b5fba6f4effee7e81bb33645fb4c1a39c888973a352b678c955d255bd",
        "第 2 次（唯一 content repair）实际请求：空槽段落对象",
    ),
    PinnedArtifact(
        "attempt_0002_acceptance",
        f"{INCIDENT_INVOCATION_DIR}/attempt-0002.content-acceptance.json",
        "a53a31940e3b06480fde5f984ad66bd861b1a676",
        "sha256:a10cbb4b4ff308404c0baf96a19c3a133166711774b8a7fd488a8abc7ba4134d",
        "第 2 次内容验收：两个 detail witness 缺失",
    ),
    PinnedArtifact(
        "attempt_0002_response",
        f"{INCIDENT_INVOCATION_DIR}/attempt-0002.provider-response.json",
        "55269bef09b67a289aceace44f33ab2670f0517b",
        "sha256:90fc83db06468205c32dddde6adbe78801e77d7ef123796ccf31efcc6fe1d118",
        "第 2 次 provider 响应（compact fragment 表面）",
    ),
    PinnedArtifact(
        "attempt_0003_completed",
        f"{INCIDENT_INVOCATION_DIR}/attempt-0003.completed.json",
        "1abd089ce6b9441875b4284674bf81c6f2171475",
        "sha256:dfc3125dcab6cf8fd0ab84213a0573e2736d6351ab29926eceadd54f9e9cfe9b",
        "第 3 次记录：预算耗尽后拒发",
    ),
    PinnedArtifact(
        "attempt_0004_completed",
        f"{INCIDENT_INVOCATION_DIR}/attempt-0004.completed.json",
        "115380a8556a78bf96ee06fd03ebfb27fbbdb9f6",
        "sha256:b6613e2894958efa4ad6e36e01685aa0c06e1dc699aa42c77c7e85f158618186",
        "第 4 次记录：拒发，非新的模型内容试验",
    ),
)

PINNED: Mapping[str, PinnedArtifact] = {item.key: item for item in _PINNED}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def archive_root() -> Path:
    root = repo_root() / ARCHIVE_RELATIVE_ROOT
    if not root.is_dir():  # pragma: no cover - 归档缺失时立即暴露
        raise IncidentArchiveDrift(f"事故归档目录不存在: {root}")
    return root


def archive_path(key: str) -> Path:
    return archive_root() / PINNED[key].path


def incident_attempt_path(filename: str) -> Path:
    """返回失败 invocation 目录下某个 attempt 文件的路径（不要求存在）。"""
    return archive_root() / INCIDENT_INVOCATION_DIR / filename


def git_blob_sha1(data: bytes) -> str:
    """按 Git 对象规则计算 blob id，避免测试依赖 git 可执行文件。"""
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def read_bytes(key: str) -> bytes:
    item = PINNED[key]
    path = archive_path(key)
    data = path.read_bytes()
    actual_sha256 = "sha256:" + hashlib.sha256(data).hexdigest()
    actual_blob = git_blob_sha1(data)
    if actual_sha256 != item.sha256 or actual_blob != item.git_blob_sha:
        raise IncidentArchiveDrift(
            "冻结归档被改动，拒绝在该 oracle 上继续回归: "
            f"{item.path} expected(blob={item.git_blob_sha}, {item.sha256}) "
            f"actual(blob={actual_blob}, {actual_sha256})"
        )
    return data


def read_json(key: str) -> Any:
    return json.loads(read_bytes(key).decode("utf-8"))
