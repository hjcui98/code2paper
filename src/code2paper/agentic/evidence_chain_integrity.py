"""Cross-artifact integrity checks for the R8/D0 evidence chain.

The individual compiler validators answer whether one artifact is well formed.
They do not answer whether the packet, fact, claim and coverage artifacts in a
run belong to the same repository snapshot and to one another.  This module is
the small, deterministic check at that boundary.

It deliberately does not infer support from names or from a profile match.
Missing provenance is a failure when the V3 route is declared enabled.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    CodeFactSetV1,
    EvidencePacketSetV3,
    load_atomic_claims_v3_or_v2,
    load_code_facts_v1,
    load_evidence_packets_v3,
)
from code2paper.agentic.intent_compiler_v2 import IntentObligationGraphV2
from code2paper.agentic.obligation_fact_alignment import ObligationCoverageReportV2
from code2paper.agentic.repo_snapshot import RepoSnapshot, load_repo_snapshot


GENERIC_PRODUCER_MARKER = "generic_research_data_plane"
PROFILE_PRODUCER_MARKER = "profile_compatibility"


class EvidenceChainIntegrityReport(BaseModel):
    """Machine-readable result of the cross-artifact D0 checks."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    v3_enabled: bool = True
    single_evidence_chain_consistent: bool = False
    generic_research_compiled_claims: bool = False
    gap_claim_noncontradiction: bool = False
    failures: tuple[str, ...] = Field(default_factory=tuple)
    evidence: tuple[str, ...] = Field(default_factory=tuple)
    repo_snapshot_id: str = ""
    project_tree_hash: str = ""
    evidence_packet_digest: str = ""
    code_fact_digest: str = ""
    claim_set_digest: str = ""
    coverage_digest: str = ""
    positive_claim_count: int = 0
    supported_fact_count: int = 0
    profile_id: str = ""
    producer: str = ""


def inspect_evidence_chain(
    *,
    repo_snapshot: RepoSnapshot | None,
    packet_set: EvidencePacketSetV3 | None,
    fact_set: CodeFactSetV1 | None,
    claim_set: AtomicClaimSetV3 | None,
    intent_graph: IntentObligationGraphV2 | None,
    coverage_report: ObligationCoverageReportV2 | None,
    generic_manifest: Mapping[str, Any] | None = None,
    profile_match: Mapping[str, Any] | None = None,
    v3_enabled: bool = True,
) -> EvidenceChainIntegrityReport:
    """Check one canonical snapshot/digest chain.

    ``generic_manifest`` is an explicit producer declaration emitted by the
    generic research route.  The producer strings on the typed sets are also
    checked, so deleting or editing only the manifest cannot turn a profile
    artifact into a generic claim set.
    """

    failures: list[str] = []
    evidence: list[str] = []
    snapshot_id = str(getattr(repo_snapshot, "snapshot_id", "") or "")
    tree_hash = str(getattr(repo_snapshot, "project_tree_hash", "") or "")
    if repo_snapshot is None:
        failures.append("repo_snapshot_missing")

    if packet_set is None:
        failures.append("evidence_packets_missing")
    if fact_set is None:
        failures.append("code_facts_missing")
    if claim_set is None:
        failures.append("atomic_claims_missing")
    if intent_graph is None:
        failures.append("intent_graph_missing")
    if coverage_report is None:
        failures.append("canonical_coverage_missing")

    packet_digest = str(getattr(packet_set, "content_digest", "") or "")
    fact_digest = str(getattr(fact_set, "content_digest", "") or "")
    claim_digest = str(getattr(claim_set, "content_digest", "") or "")
    coverage_digest = str(getattr(coverage_report, "content_digest", "") or "")

    if v3_enabled:
        for name, value in (
            ("repo_snapshot_id", snapshot_id),
            ("project_tree_hash", tree_hash),
            ("evidence_packet_digest", packet_digest),
            ("code_fact_digest", fact_digest),
            ("claim_set_digest", claim_digest),
            ("coverage_digest", coverage_digest),
        ):
            if not value:
                failures.append(f"{name}_missing")

    def compare(field: str, actual: str, expected: str) -> None:
        if actual and expected and actual != expected:
            failures.append(f"{field}_mismatch:{actual}!={expected}")

    if repo_snapshot is not None:
        compare("packet_snapshot_id", str(getattr(packet_set, "repo_snapshot_id", "") or ""), snapshot_id)
        compare("fact_snapshot_id", str(getattr(fact_set, "repo_snapshot_id", "") or ""), snapshot_id)
        compare("claim_snapshot_id", str(getattr(claim_set, "repo_snapshot_id", "") or ""), snapshot_id)
        compare("packet_project_tree_hash", str(getattr(packet_set, "project_tree_hash", "") or ""), tree_hash)
        compare("fact_project_tree_hash", str(getattr(fact_set, "project_tree_hash", "") or ""), tree_hash)
        compare("claim_project_tree_hash", str(getattr(claim_set, "project_tree_hash", "") or ""), tree_hash)

    if packet_set is not None and fact_set is not None:
        compare("fact_evidence_packet_digest", fact_set.evidence_packet_digest, packet_digest)
    if packet_set is not None and claim_set is not None:
        compare("claim_evidence_packet_digest", claim_set.evidence_packet_digest, packet_digest)
    if fact_set is not None and claim_set is not None:
        compare("claim_code_fact_digest", claim_set.code_fact_digest, fact_digest)
    if coverage_report is not None:
        if fact_set is not None:
            compare("coverage_fact_set_digest", coverage_report.fact_set_digest, fact_digest)
        if claim_set is not None:
            compare("coverage_claim_set_digest", coverage_report.claim_set_digest, claim_digest)
        if intent_graph is not None:
            compare("coverage_intent_graph_digest", coverage_report.intent_graph_digest, intent_graph.content_digest)

    supported_fact_ids: set[str] = set()
    if fact_set is not None:
        supported_fact_ids = {
            fact.fact_id
            for fact in fact_set.facts
            if fact.validation_status == "supported"
        }
        if not supported_fact_ids and getattr(claim_set, "claims", None):
            failures.append("positive_claims_have_no_supported_facts")

    if claim_set is not None:
        for claim in claim_set.claims:
            unknown = sorted(set(claim.fact_ids) - supported_fact_ids)
            if unknown:
                failures.append(
                    f"claim_unknown_supported_fact:{claim.claim_id}:{','.join(unknown)}"
                )

    # A canonical coverage item is the only accepted obligation binding.  A
    # positive claim and an explicit gap for the same obligation is a
    # contradiction, even when both artifacts are individually valid.
    gap_obligation_ids: set[str] = set()
    positive_obligation_ids: set[str] = set()
    if coverage_report is not None:
        for item in coverage_report.items:
            if item.coverage_status == "explicit_gap" or item.matched_gap_ids:
                gap_obligation_ids.add(item.obligation_id)
            if item.coverage_status in {"supported", "partial"}:
                positive_obligation_ids.add(item.obligation_id)
            if item.coverage_status == "explicit_gap" and item.matched_claim_ids:
                failures.append(
                    f"gap_item_has_positive_claims:{item.obligation_id}"
                )
    if claim_set is not None:
        for claim in claim_set.claims:
            if claim.status in {"supported", "partial"}:
                positive_obligation_ids.update(claim.covers_obligation_ids)
    contradictions = sorted(gap_obligation_ids & positive_obligation_ids)
    if contradictions:
        failures.append(
            "gap_claim_obligation_overlap:" + ",".join(contradictions)
        )

    manifest = dict(generic_manifest or {})
    producer = str(manifest.get("producer") or "")
    profile_id = str(
        manifest.get("profile_id")
        or (profile_match or {}).get("profile_id")
        or ""
    )
    profile_authoritative = bool(manifest.get("profile_authoritative", False))
    producer_versions = {
        str(getattr(value, "producer_version", "") or "")
        for value in (packet_set, fact_set, claim_set)
        if value is not None
    }
    generic_versioned = bool(producer_versions) and all(
        "generic" in version.lower() or "research_data_plane" in version.lower()
        for version in producer_versions
    )
    # Current generic sets carry the producer marker themselves.  The sidecar
    # is still preferred when present, but a valid artifact written by an
    # older generic writer must not be rejected merely because the sidecar was
    # not registered in the state map.
    generic_declared = producer == GENERIC_PRODUCER_MARKER or (
        not producer and generic_versioned
    )
    profile_declared = profile_authoritative or producer == PROFILE_PRODUCER_MARKER
    generic_claims_ok = (
        claim_set is not None
        and bool(claim_set.claims)
        and generic_declared
        and generic_versioned
        and not profile_declared
        and not failures_for_generic_chain(failures)
    )
    if v3_enabled and not generic_declared:
        failures.append("generic_producer_manifest_missing")
    if v3_enabled and not generic_versioned:
        failures.append("generic_producer_version_missing")
    if v3_enabled and not claim_set:
        failures.append("generic_claim_set_missing")
    elif v3_enabled and claim_set is not None and not claim_set.claims:
        failures.append("generic_positive_claims_missing")
    if profile_declared:
        failures.append("profile_is_authoritative")

    if snapshot_id:
        evidence.append(f"repo_snapshot_id={snapshot_id}")
    if tree_hash:
        evidence.append(f"project_tree_hash={tree_hash}")
    if packet_digest:
        evidence.append(f"evidence_packet_digest={packet_digest}")
    if fact_digest:
        evidence.append(f"code_fact_digest={fact_digest}")
    if claim_digest:
        evidence.append(f"claim_set_digest={claim_digest}")
    if coverage_digest:
        evidence.append(f"coverage_digest={coverage_digest}")
    if profile_id:
        evidence.append(f"profile_id={profile_id}")

    chain_failures = tuple(failures)
    chain_ok = not chain_failures
    noncontradiction_ok = not any(
        failure.startswith(("gap_item_has_positive_claims:", "gap_claim_obligation_overlap:"))
        for failure in chain_failures
    )
    # Generic success is intentionally independent from an empty all-gap run:
    # an explicit incomplete/gap result is safe, but it is not a compiled
    # positive generic claim chain and must not satisfy the R8 mainline gate.
    return EvidenceChainIntegrityReport(
        v3_enabled=v3_enabled,
        single_evidence_chain_consistent=chain_ok,
        generic_research_compiled_claims=generic_claims_ok,
        gap_claim_noncontradiction=noncontradiction_ok,
        failures=chain_failures,
        evidence=tuple(evidence),
        repo_snapshot_id=snapshot_id,
        project_tree_hash=tree_hash,
        evidence_packet_digest=packet_digest,
        code_fact_digest=fact_digest,
        claim_set_digest=claim_digest,
        coverage_digest=coverage_digest,
        positive_claim_count=len(getattr(claim_set, "claims", []) or []),
        supported_fact_count=len(supported_fact_ids),
        profile_id=profile_id,
        producer=producer,
    )


def failures_for_generic_chain(failures: list[str]) -> list[str]:
    """Return failures that make a positive generic chain unusable."""

    return [
        failure
        for failure in failures
        if failure.startswith(
            (
                "repo_snapshot_missing",
                "evidence_packets_missing",
                "code_facts_missing",
                "atomic_claims_missing",
                "intent_graph_missing",
                "canonical_coverage_missing",
                "packet_",
                "fact_",
                "claim_",
                "coverage_",
                "positive_claims_",
            )
        )
    ]


def inspect_evidence_chain_from_paths(
    artifact_paths: Mapping[str, str],
    *,
    v3_enabled: bool = True,
) -> EvidenceChainIntegrityReport:
    """Load the standard run artifacts and inspect their common chain.

    A malformed artifact is represented as a failed report rather than being
    raised to the acceptance caller.  This makes recheck deterministic and
    keeps a corrupted run auditable.
    """

    failures: list[str] = []

    def path_for(*keys: str) -> Path | None:
        for key in keys:
            raw = artifact_paths.get(key, "")
            if raw and Path(raw).is_file():
                return Path(raw)
        return None

    def load_json(*keys: str) -> dict[str, Any] | None:
        path = path_for(*keys)
        if path is None:
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            failures.append(f"malformed_json:{path.name}")
            return None
        return payload if isinstance(payload, dict) else None

    def load_model(loader, *keys: str):
        path = path_for(*keys)
        if path is None:
            return None
        try:
            return loader(path)
        except Exception as exc:  # noqa: BLE001 - fail closed at audit boundary
            failures.append(f"malformed_artifact:{path.name}:{type(exc).__name__}")
            return None

    repo_snapshot = None
    snapshot_path = path_for("repo_snapshot")
    if snapshot_path is not None:
        try:
            repo_snapshot = load_repo_snapshot(snapshot_path)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"malformed_artifact:{snapshot_path.name}:{type(exc).__name__}")

    packet_set = load_model(load_evidence_packets_v3, "evidence_packets_v3")
    fact_set = load_model(load_code_facts_v1, "code_facts_v1")
    claim_set = load_model(load_atomic_claims_v3_or_v2, "atomic_claims_v3", "atomic_claims_v2", "claims")
    intent_graph = load_model(
        lambda path: IntentObligationGraphV2.model_validate_json(
            path.read_text(encoding="utf-8")
        ),
        "intent_obligation_graph_v2",
        "intent_obligation_graph",
    )
    coverage_report = load_model(
        lambda path: ObligationCoverageReportV2.model_validate_json(
            path.read_text(encoding="utf-8")
        ),
        "obligation_coverage_v2",
    )
    profile_match = load_json("evidence_profile_match")
    generic_manifest = load_json(
        "generic_research_compilation_manifest",
        "evidence_chain_manifest",
    )
    result = inspect_evidence_chain(
        repo_snapshot=repo_snapshot,
        packet_set=packet_set,
        fact_set=fact_set,
        claim_set=claim_set,
        intent_graph=intent_graph,
        coverage_report=coverage_report,
        generic_manifest=generic_manifest,
        profile_match=profile_match,
        v3_enabled=v3_enabled,
    )
    if failures:
        return result.model_copy(
            update={
                "single_evidence_chain_consistent": False,
                "failures": tuple([*failures, *result.failures]),
            }
        )
    return result


__all__ = [
    "EvidenceChainIntegrityReport",
    "GENERIC_PRODUCER_MARKER",
    "PROFILE_PRODUCER_MARKER",
    "inspect_evidence_chain",
    "inspect_evidence_chain_from_paths",
]
