"""R4 wiring tests for the V3 evidence chain injection (P0 fix).

Verifies that the V3 compiled evidence (packets/facts/claims produced by
``compile_candidate_node``) is correctly:

1. Merged across obligations by ``merge_compiled_evidence`` into aggregate
   ``EvidencePacketSetV3`` / ``CodeFactSetV1`` / ``AtomicClaimSetV3`` with
   content-addressed digests.
2. Serialized to the output directory by ``write_v3_evidence_artifacts``
   as JSON files under ``out_root/artifacts/`` with the standard keys
   ``evidence_packets_v3`` / ``code_facts_v1`` / ``atomic_claims_v3``.
3. Injected into the legacy state's ``artifacts`` dict by
   ``V3GraphWrapper.invoke`` BEFORE the legacy pipeline runs, so the
   legacy writer and the R8 acceptance checker can consume them.
4. Merged into the legacy payload AFTER the legacy pipeline runs, so
   downstream consumers (R8 checker) can find them even when the legacy
   pipeline did not produce its own evidence artifacts.
5. Extracted from the legacy state via ``_extract_out_root`` which
   handles dict / object / None inputs gracefully.

This closes the P0 gap where V3 research results did not enter the main
body evidence chain (v3_runtime.py ran V3 then legacy separately, only
merging decisions).
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from code2paper.agentic.behavior_graph import (
    BehaviorNodeV1,
    CodeBehaviorGraphV1,
)
from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    AtomicClaimV3,
    CodeFactSetV1,
    CodeFactV1,
    EvidencePacketSetV3,
    EvidencePacketV3,
)
from code2paper.agentic.research_graph import CompiledEvidence
from code2paper.agentic.v3_runtime import (
    V3GraphWrapper,
    _extract_out_root,
    merge_compiled_evidence,
    write_v3_evidence_artifacts,
)


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


_REPO_SNAPSHOT_ID = "repo:test-snapshot"
_PROJECT_TREE_HASH = "sha256:tree"


def _node(
    *,
    node_id: str = "node:test",
    source_span_id: str = "span:train.py:1:10",
    predicate: str = "READ",
) -> BehaviorNodeV1:
    return BehaviorNodeV1(
        node_id=node_id,
        symbol_id="sym:train.train",
        operation_id="op-test",
        predicate=predicate,
        operands=("x",),
        result="y",
        guard="",
        source_span_id=source_span_id,
        source_authority="executable_hard",
    )


def _packet(
    *,
    packet_id: str = "pkt-obl-1-abc",
    obligation_tag: str = "obl-1",
) -> EvidencePacketV3:
    # EvidencePacketV3 validator requires anchor_span_ids to be a subset
    # of span ids in ``spans``.  Use empty anchor_span_ids (with empty
    # spans) so the packet is valid without building full span objects.
    return EvidencePacketV3(
        packet_id=packet_id,
        obligation_tags=[obligation_tag],
        scope="sym:train.train",
        anchor_span_ids=[],
        relation_span_ids=[],
        semantic_span_ids=[],
        spans=[],
        relations=[],
        conditions=[],
        composition_rationale="",
        rejected_candidates=[],
        source_digest="sha256:packet-1",
    )


def _fact(
    *,
    fact_id: str = "fact-obl-1-1",
    scope: str = "sym:train.train",
) -> CodeFactV1:
    return CodeFactV1(
        fact_id=fact_id,
        subject="sym:train.train",
        predicate="reads",
        object="optimizer",
        conditions=[],
        scope=scope,
        direct_span_ids=["span:train.py:1:10"],
        relation_span_ids=[],
        relation_evidence_ids=[],
        exact_source_digest="sha256:fact-1",
        canonical_identity="sha256:identity-1",
        validation_status="supported",
        validation_failures=[],
    )


def _claim(
    *,
    claim_id: str = "claim-obl-1-1",
    fact_id: str = "fact-obl-1-1",
    obligation_id: str = "obl-1",
) -> AtomicClaimV3:
    return AtomicClaimV3(
        claim_id=claim_id,
        canonical_text="sym:train.train reads optimizer",
        claim_kind="implementation_behavior",
        fact_ids=[fact_id],
        covers_obligation_ids=[obligation_id],
        direct_evidence_ids=["span:train.py:1:10"],
        relation_evidence_ids=[],
        required_qualifiers=[],
        unsupported_author_fragments=[],
        allowed_wording_boundary="exact behavior predicate and operands",
        canonical_identity="sha256:identity-1",
        status="supported",
    )


def _packet_set(packets: list[EvidencePacketV3]) -> EvidencePacketSetV3:
    import hashlib

    payload = [p.model_dump(mode="json") for p in packets]
    digest = "sha256:" + hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return EvidencePacketSetV3(
        repo_snapshot_id=_REPO_SNAPSHOT_ID,
        project_tree_hash=_PROJECT_TREE_HASH,
        packets=packets,
        content_digest=digest,
    )


def _fact_set(
    facts: list[CodeFactV1],
    *,
    evidence_packet_digest: str = "sha256:packets",
) -> CodeFactSetV1:
    import hashlib

    payload = [f.model_dump(mode="json") for f in facts]
    digest = "sha256:" + hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return CodeFactSetV1(
        repo_snapshot_id=_REPO_SNAPSHOT_ID,
        project_tree_hash=_PROJECT_TREE_HASH,
        evidence_packet_digest=evidence_packet_digest,
        facts=facts,
        content_digest=digest,
    )


def _claim_set(
    claims: list[AtomicClaimV3],
    *,
    evidence_packet_digest: str = "sha256:packets",
    code_fact_digest: str = "sha256:facts",
) -> AtomicClaimSetV3:
    import hashlib

    payload = {
        "claims": [c.model_dump(mode="json") for c in claims],
        "explicit_code_gaps": [],
    }
    digest = "sha256:" + hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return AtomicClaimSetV3(
        repo_snapshot_id=_REPO_SNAPSHOT_ID,
        project_tree_hash=_PROJECT_TREE_HASH,
        evidence_packet_digest=evidence_packet_digest,
        code_fact_digest=code_fact_digest,
        claims=claims,
        explicit_code_gaps=[],
        content_digest=digest,
    )


def _compiled_evidence(
    *,
    obligation_id: str = "obl-1",
) -> CompiledEvidence:
    return CompiledEvidence(
        obligation_id=obligation_id,
        packet_set=_packet_set([_packet(obligation_tag=obligation_id)]),
        fact_set=_fact_set([_fact(scope=f"sym:{obligation_id}")]),
        claim_set=_claim_set([_claim(obligation_id=obligation_id)]),
    )


# ---------------------------------------------------------------------------
# 1. _extract_out_root
# ---------------------------------------------------------------------------


class ExtractOutRootTests(unittest.TestCase):
    """``_extract_out_root`` must handle dict / object / None inputs."""

    def test_dict_with_out_root_string(self) -> None:
        result = _extract_out_root({"out_root": "/tmp/foo"})
        self.assertEqual(result, Path("/tmp/foo"))

    def test_dict_with_out_root_path(self) -> None:
        result = _extract_out_root({"out_root": Path("/tmp/foo")})
        self.assertEqual(result, Path("/tmp/foo"))

    def test_dict_without_out_root_returns_none(self) -> None:
        result = _extract_out_root({"other": "value"})
        self.assertIsNone(result)

    def test_dict_with_empty_out_root_returns_none(self) -> None:
        result = _extract_out_root({"out_root": ""})
        self.assertIsNone(result)

    def test_dict_with_whitespace_out_root_returns_none(self) -> None:
        result = _extract_out_root({"out_root": "   "})
        self.assertIsNone(result)

    def test_object_with_out_root_attribute(self) -> None:
        class _State:
            out_root = Path("/tmp/obj")

        result = _extract_out_root(_State())
        self.assertEqual(result, Path("/tmp/obj"))

    def test_object_without_out_root_attribute_returns_none(self) -> None:
        class _State:
            pass

        result = _extract_out_root(_State())
        self.assertIsNone(result)

    def test_none_returns_none(self) -> None:
        result = _extract_out_root(None)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# 2. merge_compiled_evidence
# ---------------------------------------------------------------------------


class MergeCompiledEvidenceTests(unittest.TestCase):
    """``merge_compiled_evidence`` aggregates per-obligation evidence into
    content-addressed sets."""

    def test_empty_dict_returns_none_tuple(self) -> None:
        packets, facts, claims = merge_compiled_evidence(
            {},
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )
        self.assertIsNone(packets)
        self.assertIsNone(facts)
        self.assertIsNone(claims)

    def test_single_obligation_merges_into_one_set(self) -> None:
        ce = _compiled_evidence(obligation_id="obl-1")
        packets, facts, claims = merge_compiled_evidence(
            {"obl-1": ce},
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )
        self.assertIsNotNone(packets)
        self.assertIsNotNone(facts)
        self.assertIsNotNone(claims)
        self.assertEqual(len(packets.packets), 1)
        self.assertEqual(len(facts.facts), 1)
        self.assertEqual(len(claims.claims), 1)

    def test_multiple_obligations_merge_into_aggregate_sets(self) -> None:
        ce1 = _compiled_evidence(obligation_id="obl-1")
        ce2 = _compiled_evidence(obligation_id="obl-2")
        packets, facts, claims = merge_compiled_evidence(
            {"obl-1": ce1, "obl-2": ce2},
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )
        self.assertEqual(len(packets.packets), 2)
        self.assertEqual(len(facts.facts), 2)
        self.assertEqual(len(claims.claims), 2)

    def test_merged_sets_carry_content_digest(self) -> None:
        ce = _compiled_evidence(obligation_id="obl-1")
        packets, facts, claims = merge_compiled_evidence(
            {"obl-1": ce},
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )
        self.assertTrue(packets.content_digest.startswith("sha256:"))
        self.assertTrue(facts.content_digest.startswith("sha256:"))
        self.assertTrue(claims.content_digest.startswith("sha256:"))

    def test_merged_sets_carry_repo_snapshot_id(self) -> None:
        ce = _compiled_evidence(obligation_id="obl-1")
        packets, facts, claims = merge_compiled_evidence(
            {"obl-1": ce},
            repo_snapshot_id="repo:custom",
            project_tree_hash="sha256:custom",
        )
        self.assertEqual(packets.repo_snapshot_id, "repo:custom")
        self.assertEqual(facts.repo_snapshot_id, "repo:custom")
        self.assertEqual(claims.repo_snapshot_id, "repo:custom")
        self.assertEqual(packets.project_tree_hash, "sha256:custom")

    def test_same_inputs_produce_same_digests(self) -> None:
        """Determinism: merging the same compiled evidence twice must
        produce the same content digests."""

        def _merge() -> tuple[str, str, str]:
            ce = _compiled_evidence(obligation_id="obl-1")
            packets, facts, claims = merge_compiled_evidence(
                {"obl-1": ce},
                repo_snapshot_id=_REPO_SNAPSHOT_ID,
                project_tree_hash=_PROJECT_TREE_HASH,
            )
            return (packets.content_digest, facts.content_digest, claims.content_digest)

        self.assertEqual(_merge(), _merge())

    def test_different_obligations_produce_different_digests(self) -> None:
        ce1 = _compiled_evidence(obligation_id="obl-1")
        ce2 = _compiled_evidence(obligation_id="obl-2")
        p1, f1, c1 = merge_compiled_evidence(
            {"obl-1": ce1},
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )
        p2, f2, c2 = merge_compiled_evidence(
            {"obl-2": ce2},
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )
        self.assertNotEqual(p1.content_digest, p2.content_digest)
        self.assertNotEqual(f1.content_digest, f2.content_digest)
        self.assertNotEqual(c1.content_digest, c2.content_digest)


# ---------------------------------------------------------------------------
# 3. write_v3_evidence_artifacts
# ---------------------------------------------------------------------------


class WriteV3EvidenceArtifactsTests(unittest.TestCase):
    """``write_v3_evidence_artifacts`` serializes the merged sets to
    ``out_root/artifacts/`` as JSON files."""

    def test_writes_three_files_when_all_sets_present(self) -> None:
        ce = _compiled_evidence(obligation_id="obl-1")
        packets, facts, claims = merge_compiled_evidence(
            {"obl-1": ce},
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_v3_evidence_artifacts(
                tmp,
                packet_set=packets,
                fact_set=facts,
                claim_set=claims,
            )
            self.assertEqual(len(paths), 3)
            self.assertIn("evidence_packets_v3", paths)
            self.assertIn("code_facts_v1", paths)
            self.assertIn("atomic_claims_v3", paths)
            # All paths must point to existing files under artifacts/.
            artifacts_dir = Path(tmp) / "artifacts"
            for key, path in paths.items():
                self.assertTrue(Path(path).exists(), f"{key} file missing")
                self.assertTrue(Path(path).is_file())
                self.assertTrue(Path(path).parent == artifacts_dir)

    def test_file_names_use_standard_keys_with_suffix(self) -> None:
        ce = _compiled_evidence(obligation_id="obl-1")
        packets, facts, claims = merge_compiled_evidence(
            {"obl-1": ce},
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_v3_evidence_artifacts(
                tmp,
                packet_set=packets,
                fact_set=facts,
                claim_set=claims,
                suffix="_v3",
            )
            self.assertTrue(paths["evidence_packets_v3"].endswith("evidence_packets_v3_v3.json"))
            self.assertTrue(paths["code_facts_v1"].endswith("code_facts_v1_v3.json"))
            self.assertTrue(paths["atomic_claims_v3"].endswith("atomic_claims_v3_v3.json"))

    def test_custom_suffix_changes_file_names(self) -> None:
        ce = _compiled_evidence(obligation_id="obl-1")
        packets, facts, claims = merge_compiled_evidence(
            {"obl-1": ce},
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_v3_evidence_artifacts(
                tmp,
                packet_set=packets,
                fact_set=facts,
                claim_set=claims,
                suffix="_run42",
            )
            self.assertTrue(paths["evidence_packets_v3"].endswith("evidence_packets_v3_run42.json"))

    def test_none_sets_are_skipped(self) -> None:
        ce = _compiled_evidence(obligation_id="obl-1")
        packets, facts, claims = merge_compiled_evidence(
            {"obl-1": ce},
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )
        with tempfile.TemporaryDirectory() as tmp:
            # Pass only packets, None for the rest.
            paths = write_v3_evidence_artifacts(
                tmp,
                packet_set=packets,
                fact_set=None,
                claim_set=None,
            )
            self.assertEqual(len(paths), 1)
            self.assertIn("evidence_packets_v3", paths)
            self.assertNotIn("code_facts_v1", paths)
            self.assertNotIn("atomic_claims_v3", paths)

    def test_all_none_returns_empty_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_v3_evidence_artifacts(
                tmp,
                packet_set=None,
                fact_set=None,
                claim_set=None,
            )
            self.assertEqual(paths, {})

    def test_written_files_contain_valid_json(self) -> None:
        ce = _compiled_evidence(obligation_id="obl-1")
        packets, facts, claims = merge_compiled_evidence(
            {"obl-1": ce},
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_v3_evidence_artifacts(
                tmp,
                packet_set=packets,
                fact_set=facts,
                claim_set=claims,
            )
            for key, path in paths.items():
                data = json.loads(Path(path).read_text(encoding="utf-8"))
                self.assertIsInstance(data, dict)
                # Every set must carry repo_snapshot_id and content_digest.
                self.assertIn("repo_snapshot_id", data)
                self.assertIn("content_digest", data)

    def test_artifacts_dir_created_when_missing(self) -> None:
        ce = _compiled_evidence(obligation_id="obl-1")
        packets, facts, claims = merge_compiled_evidence(
            {"obl-1": ce},
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )
        with tempfile.TemporaryDirectory() as tmp:
            # artifacts/ does not exist yet.
            self.assertFalse((Path(tmp) / "artifacts").exists())
            write_v3_evidence_artifacts(
                tmp,
                packet_set=packets,
                fact_set=facts,
                claim_set=claims,
            )
            # Now it must exist.
            self.assertTrue((Path(tmp) / "artifacts").is_dir())


# ---------------------------------------------------------------------------
# 4. V3GraphWrapper.invoke evidence chain injection
# ---------------------------------------------------------------------------


class V3GraphWrapperEvidenceChainTests(unittest.TestCase):
    """``V3GraphWrapper.invoke`` must inject V3 artifact paths into the
    legacy state BEFORE the legacy pipeline runs, so the legacy writer
    can consume them.  This is the P0 fix for the V3 evidence chain."""

    def _fake_runtime_with_compiled_evidence(
        self,
        compiled_evidence: dict[str, CompiledEvidence],
    ) -> MagicMock:
        """Build a fake V3 runtime whose loop_state carries the given
        compiled evidence."""
        runtime = MagicMock()
        runtime.repo_snapshot = MagicMock(
            snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )
        return runtime

    def _make_fake_v3_result(
        self,
        compiled_evidence: dict[str, CompiledEvidence],
    ) -> MagicMock:
        """Build a fake ResearchLoopResult with compiled_evidence."""
        result = MagicMock()
        result.decision_trace = []
        loop_state = MagicMock()
        loop_state.compiled_evidence = compiled_evidence
        result.loop_state = loop_state
        return result

    def test_invoke_injects_artifact_paths_into_legacy_state(self) -> None:
        """The V3 artifact paths must appear in the state passed to the
        legacy pipeline's ``invoke``."""

        ce = _compiled_evidence(obligation_id="obl-1")
        runtime = self._fake_runtime_with_compiled_evidence({"obl-1": ce})

        # Capture the state passed to legacy.invoke.
        captured_state: dict[str, Any] = {}

        def _legacy_invoke(state, *args, **kwargs):
            captured_state.update(state)
            return {"decisions": [], "tool_call_trace_refs": []}

        legacy = MagicMock()
        legacy.invoke.side_effect = _legacy_invoke

        wrapper = V3GraphWrapper(
            v3_runtime=runtime, legacy_graph=legacy, max_research_turns=5
        )

        import code2paper.agentic.v3_runtime as v3_mod

        original = v3_mod.run_v3_research_phase
        v3_mod.run_v3_research_phase = lambda *a, **kw: self._make_fake_v3_result(
            {"obl-1": ce}
        )
        # Provide out_root so artifacts are written to disk.
        with tempfile.TemporaryDirectory() as tmp:
            try:
                wrapper.invoke({"out_root": tmp, "artifacts": {}})
            finally:
                v3_mod.run_v3_research_phase = original

            # The state captured by legacy.invoke must contain the V3
            # artifact paths under the standard keys.
            self.assertIn("artifacts", captured_state)
            artifacts = captured_state["artifacts"]
            self.assertIn("evidence_packets_v3", artifacts)
            self.assertIn("code_facts_v1", artifacts)
            self.assertIn("atomic_claims_v3", artifacts)
            # The paths must point to existing files.
            for key in ("evidence_packets_v3", "code_facts_v1", "atomic_claims_v3"):
                self.assertTrue(Path(artifacts[key]).exists(), f"{key} file missing")

    def test_invoke_does_not_overwrite_existing_artifact_paths(self) -> None:
        """When the caller already pointed at a specific evidence file,
        the wrapper must respect that choice (use ``setdefault``)."""

        ce = _compiled_evidence(obligation_id="obl-1")
        runtime = self._fake_runtime_with_compiled_evidence({"obl-1": ce})

        captured_state: dict[str, Any] = {}

        def _legacy_invoke(state, *args, **kwargs):
            captured_state.update(state)
            return {"decisions": [], "tool_call_trace_refs": []}

        legacy = MagicMock()
        legacy.invoke.side_effect = _legacy_invoke

        wrapper = V3GraphWrapper(
            v3_runtime=runtime, legacy_graph=legacy, max_research_turns=5
        )

        import code2paper.agentic.v3_runtime as v3_mod

        original = v3_mod.run_v3_research_phase
        v3_mod.run_v3_research_phase = lambda *a, **kw: self._make_fake_v3_result(
            {"obl-1": ce}
        )
        # Pre-existing artifact path that must NOT be overwritten.
        existing_path = "/custom/existing/evidence_packets_v3.json"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                wrapper.invoke({
                    "out_root": tmp,
                    "artifacts": {"evidence_packets_v3": existing_path},
                })
        finally:
            v3_mod.run_v3_research_phase = original

        # The pre-existing path must be preserved.
        self.assertEqual(
            captured_state["artifacts"]["evidence_packets_v3"],
            existing_path,
        )

    def test_invoke_merges_artifact_paths_into_legacy_payload(self) -> None:
        """After the legacy pipeline runs, the wrapper must also merge
        the V3 artifact paths into the legacy payload so downstream
        consumers (R8 checker) can find them."""

        ce = _compiled_evidence(obligation_id="obl-1")
        runtime = self._fake_runtime_with_compiled_evidence({"obl-1": ce})

        # Legacy returns a payload without evidence artifacts.
        legacy = MagicMock()
        legacy.invoke.return_value = {
            "decisions": [],
            "tool_call_trace_refs": [],
            "artifacts": {"some_other_artifact": "/path/to/other.json"},
        }

        wrapper = V3GraphWrapper(
            v3_runtime=runtime, legacy_graph=legacy, max_research_turns=5
        )

        import code2paper.agentic.v3_runtime as v3_mod

        original = v3_mod.run_v3_research_phase
        v3_mod.run_v3_research_phase = lambda *a, **kw: self._make_fake_v3_result(
            {"obl-1": ce}
        )
        try:
            with tempfile.TemporaryDirectory() as tmp:
                payload = wrapper.invoke({"out_root": tmp, "artifacts": {}})
        finally:
            v3_mod.run_v3_research_phase = original

        # The payload must contain both the legacy artifact and the V3
        # evidence artifacts.
        self.assertIn("some_other_artifact", payload["artifacts"])
        self.assertIn("evidence_packets_v3", payload["artifacts"])
        self.assertIn("code_facts_v1", payload["artifacts"])
        self.assertIn("atomic_claims_v3", payload["artifacts"])

    def test_invoke_skips_artifact_writing_when_no_out_root(self) -> None:
        """When the state has no ``out_root``, the wrapper must skip
        artifact serialization (but still run the legacy pipeline)."""

        ce = _compiled_evidence(obligation_id="obl-1")
        runtime = self._fake_runtime_with_compiled_evidence({"obl-1": ce})

        legacy = MagicMock()
        legacy.invoke.return_value = {"decisions": [], "tool_call_trace_refs": []}

        wrapper = V3GraphWrapper(
            v3_runtime=runtime, legacy_graph=legacy, max_research_turns=5
        )

        import code2paper.agentic.v3_runtime as v3_mod

        original = v3_mod.run_v3_research_phase
        v3_mod.run_v3_research_phase = lambda *a, **kw: self._make_fake_v3_result(
            {"obl-1": ce}
        )
        try:
            # No out_root in state.
            payload = wrapper.invoke({"some": "state"})
        finally:
            v3_mod.run_v3_research_phase = original

        # Legacy still ran.
        legacy.invoke.assert_called_once()
        # No V3 artifacts in the payload (none were written).
        artifacts = payload.get("artifacts") or {}
        self.assertNotIn("evidence_packets_v3", artifacts)

    def test_invoke_skips_artifact_writing_when_no_compiled_evidence(self) -> None:
        """When V3 research produced no compiled evidence, the wrapper
        must skip artifact serialization."""

        runtime = self._fake_runtime_with_compiled_evidence({})

        legacy = MagicMock()
        legacy.invoke.return_value = {"decisions": [], "tool_call_trace_refs": []}

        wrapper = V3GraphWrapper(
            v3_runtime=runtime, legacy_graph=legacy, max_research_turns=5
        )

        import code2paper.agentic.v3_runtime as v3_mod

        original = v3_mod.run_v3_research_phase
        # Empty compiled_evidence.
        v3_mod.run_v3_research_phase = lambda *a, **kw: self._make_fake_v3_result({})
        try:
            with tempfile.TemporaryDirectory() as tmp:
                payload = wrapper.invoke({"out_root": tmp, "artifacts": {}})
        finally:
            v3_mod.run_v3_research_phase = original

        # Legacy still ran.
        legacy.invoke.assert_called_once()
        # No V3 artifacts in the payload.
        artifacts = payload.get("artifacts") or {}
        self.assertNotIn("evidence_packets_v3", artifacts)

    def test_invoke_falls_back_gracefully_when_v3_research_raises(self) -> None:
        """When V3 research raises, the wrapper must still run the legacy
        pipeline and not inject any V3 artifacts."""

        runtime = self._fake_runtime_with_compiled_evidence({})

        legacy = MagicMock()
        legacy.invoke.return_value = {"decisions": [], "tool_call_trace_refs": []}

        wrapper = V3GraphWrapper(
            v3_runtime=runtime, legacy_graph=legacy, max_research_turns=5
        )

        import code2paper.agentic.v3_runtime as v3_mod

        original = v3_mod.run_v3_research_phase

        def _raise(*a, **kw):
            raise RuntimeError("v3 blew up")

        v3_mod.run_v3_research_phase = _raise
        try:
            with tempfile.TemporaryDirectory() as tmp:
                payload = wrapper.invoke({"out_root": tmp, "artifacts": {}})
        finally:
            v3_mod.run_v3_research_phase = original

        # Legacy still ran.
        legacy.invoke.assert_called_once()
        # No V3 artifacts in the payload.
        artifacts = payload.get("artifacts") or {}
        self.assertNotIn("evidence_packets_v3", artifacts)
        self.assertNotIn("code_facts_v1", artifacts)
        self.assertNotIn("atomic_claims_v3", artifacts)

    def test_invoke_writes_valid_json_artifacts(self) -> None:
        """The written V3 artifact files must contain valid JSON that
        round-trips through the Pydantic models."""

        ce = _compiled_evidence(obligation_id="obl-1")
        runtime = self._fake_runtime_with_compiled_evidence({"obl-1": ce})

        legacy = MagicMock()
        legacy.invoke.return_value = {"decisions": [], "tool_call_trace_refs": []}

        wrapper = V3GraphWrapper(
            v3_runtime=runtime, legacy_graph=legacy, max_research_turns=5
        )

        import code2paper.agentic.v3_runtime as v3_mod

        original = v3_mod.run_v3_research_phase
        v3_mod.run_v3_research_phase = lambda *a, **kw: self._make_fake_v3_result(
            {"obl-1": ce}
        )
        try:
            with tempfile.TemporaryDirectory() as tmp:
                payload = wrapper.invoke({"out_root": tmp, "artifacts": {}})
                artifacts = payload["artifacts"]
                # Read and validate each artifact file.
                packet_data = json.loads(
                    Path(artifacts["evidence_packets_v3"]).read_text(encoding="utf-8")
                )
                fact_data = json.loads(
                    Path(artifacts["code_facts_v1"]).read_text(encoding="utf-8")
                )
                claim_data = json.loads(
                    Path(artifacts["atomic_claims_v3"]).read_text(encoding="utf-8")
                )
                # Round-trip through the Pydantic models.
                EvidencePacketSetV3.model_validate(packet_data)
                CodeFactSetV1.model_validate(fact_data)
                AtomicClaimSetV3.model_validate(claim_data)
        finally:
            v3_mod.run_v3_research_phase = original


# ---------------------------------------------------------------------------
# 5. End-to-end: compile -> merge -> write -> read back
# ---------------------------------------------------------------------------


class TestEndToEndEvidenceChain:
    """End-to-end: compile evidence via ``compile_candidate_node``,
    merge via ``merge_compiled_evidence``, write via
    ``write_v3_evidence_artifacts``, then read back and validate."""

    def test_compile_merge_write_roundtrip(self, tmp_path: Path) -> None:
        from code2paper.agentic.research_nodes import (
            BudgetPolicyV1,
            InformationGainTracker,
            compile_candidate_node,
        )
        from code2paper.agentic.research_graph import initial_loop_state
        from code2paper.agentic.research_models import (
            GlobalSafetyBudgetV1,
            ResearchAgendaItemV1,
            ResearchAgendaV1,
        )
        from code2paper.agentic.repo_snapshot import RepoSnapshot, build_repo_snapshot

        # Build a tiny fixture repo.
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / "train.py").write_text(
            "def train():\n    x = 1\n    return x\n",
            encoding="utf-8",
        )
        snapshot = build_repo_snapshot(repo_root)

        obl = ResearchAgendaItemV1(
            obligation_id="obl-e2e",
            priority="must_cover",
            status="in_progress",
            candidate_symbol_ids=("train.py:train",),
            candidate_behavior_node_ids=[],
            missing_information=[],
            typed_behavior_targets=[],
        )
        agenda = ResearchAgendaV1(
            run_id="run-e2e",
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
            items=[obl],
        )
        runtime = MagicMock()
        runtime.run_id = "run-e2e"
        runtime.repo_snapshot = snapshot
        runtime.agenda = agenda

        from code2paper.agentic.research_nodes import ResearchGraphRuntime

        runtime = ResearchGraphRuntime(
            run_id="run-e2e",
            repo_snapshot=snapshot,
            agenda=agenda,
            budget_policy=BudgetPolicyV1(),
            global_safety_budget=GlobalSafetyBudgetV1(),
        )

        # Build a behavior graph with a node matching train.py.
        node = _node(
            node_id="node:e2e",
            source_span_id="span:train.py:1:3",
        )
        bg = CodeBehaviorGraphV1(
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
            language="python",
            nodes=[node],
            relations=[],
            unresolved_relations=[],
        ).with_digest()

        gain = InformationGainTracker()
        state = {
            "run_id": "run-e2e",
            "repo_snapshot_id": snapshot.snapshot_id,
            "project_tree_hash": snapshot.project_tree_hash,
            "active_obligation_id": "obl-e2e",
            "status": "researching",
        }
        update = compile_candidate_node(
            state,
            runtime=runtime,
            behavior_graph=bg,
            active_obligation_id="obl-e2e",
            gain_tracker=gain,
        )
        assert "_compiled_evidence" in update
        compiled_dict = update["_compiled_evidence"]
        ce = CompiledEvidence(
            obligation_id=compiled_dict["obligation_id"],
            packet_set=compiled_dict["packet_set"],
            fact_set=compiled_dict["fact_set"],
            claim_set=compiled_dict["claim_set"],
        )

        # Merge.
        packets, facts, claims = merge_compiled_evidence(
            {"obl-e2e": ce},
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
        )
        assert packets is not None
        assert facts is not None
        assert claims is not None

        # Write.
        out_root = tmp_path / "out"
        out_root.mkdir()
        paths = write_v3_evidence_artifacts(
            out_root,
            packet_set=packets,
            fact_set=facts,
            claim_set=claims,
        )
        assert len(paths) == 3

        # Read back and validate.
        packet_data = json.loads(
            Path(paths["evidence_packets_v3"]).read_text(encoding="utf-8")
        )
        fact_data = json.loads(
            Path(paths["code_facts_v1"]).read_text(encoding="utf-8")
        )
        claim_data = json.loads(
            Path(paths["atomic_claims_v3"]).read_text(encoding="utf-8")
        )
        EvidencePacketSetV3.model_validate(packet_data)
        CodeFactSetV1.model_validate(fact_data)
        AtomicClaimSetV3.model_validate(claim_data)

        # The merged set digests must match the written file digests.
        assert packet_data["content_digest"] == packets.content_digest
        assert fact_data["content_digest"] == facts.content_digest
        assert claim_data["content_digest"] == claims.content_digest
