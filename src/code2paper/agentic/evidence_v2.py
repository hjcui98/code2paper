from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.repo_snapshot import RepoSnapshot
from code2paper.core.schemas import RawEvidencePack


class EvidenceV2Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceSpanV2(EvidenceV2Model):
    evidence_id: str
    snapshot_id: str
    project_tree_hash: str
    path: str
    symbol: str = ""
    line_start: int
    line_end: int
    exact_excerpt: str
    excerpt_digest: str
    file_digest: str
    source_type: str
    strength: Literal["hard", "soft", "semantic_hint"] = "hard"
    extraction_method: str = "path_line_exact_excerpt"
    producer_version: str = "code2paper-agentic-p1"
    derived_from_evidence_ids: list[str] = Field(default_factory=list)
    runtime_trace_ref: str = ""
    status: Literal["valid", "missing", "invalid"] = "valid"

    @model_validator(mode="after")
    def _valid_span_has_exact_identity(self) -> "EvidenceSpanV2":
        if self.status == "valid" and (not self.exact_excerpt or not self.file_digest):
            raise ValueError("valid EvidenceSpanV2 requires exact excerpt and file digest")
        return self


class EvidenceSnapshotV2(EvidenceV2Model):
    schema_version: str = "2.0"
    snapshot_version: int = 1
    evidence_snapshot_id: str
    repo_snapshot_id: str
    project_tree_hash: str
    producer_version: str = "code2paper-agentic-p1"
    parent_evidence_snapshot_id: str = ""
    repair_reason: str = "initial_v1_compatibility_conversion"
    spans: list[EvidenceSpanV2] = Field(default_factory=list)
    added_evidence_ids: list[str] = Field(default_factory=list)
    removed_evidence_ids: list[str] = Field(default_factory=list)
    content_digest: str
    frozen: bool = True


def build_evidence_snapshot_v2(
    raw_evidence: RawEvidencePack,
    repo_snapshot: RepoSnapshot,
    *,
    parent: EvidenceSnapshotV2 | None = None,
    repair_reason: str = "initial_v1_compatibility_conversion",
) -> EvidenceSnapshotV2:
    root = Path(repo_snapshot.project_root).resolve()
    file_by_path = {item.path: item for item in repo_snapshot.included_files if item.kind == "file"}
    spans: list[EvidenceSpanV2] = []
    for item in raw_evidence.evidence_items:
        relative = Path(str(item.path or "")).as_posix().lstrip("/")
        snapshot_file = file_by_path.get(relative)
        excerpt = _read_exact_excerpt(root, relative, item.line_start, item.line_end)
        status = "valid" if snapshot_file is not None and excerpt else "missing"
        spans.append(
            EvidenceSpanV2(
                evidence_id=item.evidence_id,
                snapshot_id=repo_snapshot.snapshot_id,
                project_tree_hash=repo_snapshot.project_tree_hash,
                path=relative,
                symbol=str(item.symbol or ""),
                line_start=item.line_start,
                line_end=item.line_end,
                exact_excerpt=excerpt,
                excerpt_digest=_digest_text(excerpt),
                file_digest=snapshot_file.content_digest if snapshot_file else "",
                source_type=str(getattr(item.source_type, "value", item.source_type)),
                strength="hard" if status == "valid" else "semantic_hint",
                status=status,
            )
        )
    content_payload = [span.model_dump(mode="json") for span in spans]
    digest = _digest_json(content_payload)
    parent_ids = {span.evidence_id for span in parent.spans} if parent else set()
    current_ids = {span.evidence_id for span in spans}
    snapshot_version = parent.snapshot_version + 1 if parent else 1
    parent_snapshot_id = parent.evidence_snapshot_id if parent else ""
    identity_digest = _digest_json(
        {
            "repo_snapshot_id": repo_snapshot.snapshot_id,
            "project_tree_hash": repo_snapshot.project_tree_hash,
            "snapshot_version": snapshot_version,
            "parent_evidence_snapshot_id": parent_snapshot_id,
            "repair_reason": repair_reason,
            "content_digest": digest,
        }
    )
    return EvidenceSnapshotV2(
        snapshot_version=snapshot_version,
        evidence_snapshot_id="evidence:" + identity_digest.removeprefix("sha256:"),
        repo_snapshot_id=repo_snapshot.snapshot_id,
        project_tree_hash=repo_snapshot.project_tree_hash,
        parent_evidence_snapshot_id=parent_snapshot_id,
        repair_reason=repair_reason,
        spans=spans,
        added_evidence_ids=sorted(current_ids - parent_ids),
        removed_evidence_ids=sorted(parent_ids - current_ids),
        content_digest=digest,
    )


def validate_evidence_snapshot_round_trip(snapshot: EvidenceSnapshotV2, repo: RepoSnapshot) -> list[str]:
    root = Path(repo.project_root).resolve()
    failures: list[str] = []
    for span in snapshot.spans:
        if span.status != "valid":
            failures.append(f"invalid_span:{span.evidence_id}")
            continue
        excerpt = _read_exact_excerpt(root, span.path, span.line_start, span.line_end)
        if _digest_text(excerpt) != span.excerpt_digest:
            failures.append(f"excerpt_digest_mismatch:{span.evidence_id}")
        file_entry = next((item for item in repo.included_files if item.path == span.path), None)
        if file_entry is None or file_entry.content_digest != span.file_digest:
            failures.append(f"file_digest_mismatch:{span.evidence_id}")
    return failures


def write_evidence_snapshot_v2(path: str | Path, snapshot: EvidenceSnapshotV2) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def load_evidence_snapshot_v2(path: str | Path) -> EvidenceSnapshotV2:
    return EvidenceSnapshotV2.model_validate_json(Path(path).read_text(encoding="utf-8"))


def _read_exact_excerpt(root: Path, relative: str, line_start: int, line_end: int) -> str:
    if not relative or line_start <= 0 or line_end < line_start:
        return ""
    try:
        candidate = (root / relative).resolve()
        candidate.relative_to(root)
        lines = candidate.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    except (OSError, ValueError):
        return ""
    return "".join(lines[line_start - 1 : min(line_end, len(lines))])


def _digest_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _digest_json(value) -> str:
    return _digest_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
