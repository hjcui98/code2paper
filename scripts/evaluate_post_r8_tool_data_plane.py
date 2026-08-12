#!/usr/bin/env python3
"""Run a source-backed D1 search/read -> packet/fact/claim acceptance chain.

This fixture deliberately starts without a project evidence profile.  The
only positive records are produced after the research tools search and read a
fresh snapshot, update the behavior graph, and execute the persisted generic
data-plane validators.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from code2paper.agentic.behavior_graph import CodeBehaviorGraphV1
from code2paper.agentic.evidence_compiler_v3 import (
    EvidencePacketV3,
    GENERIC_RESEARCH_PRODUCER_VERSION,
    load_atomic_claims_v3,
    load_code_facts_v1,
)
from code2paper.agentic.repo_snapshot import build_repo_snapshot
from code2paper.agentic.research_models import (
    ResearchAgendaItemV1,
    ResearchAgendaV1,
    ResearchToolCallV1,
)
from code2paper.agentic.research_nodes import ResearchGraphRuntime, behavior_graph_updater_node
from code2paper.agentic.research_tools import (
    RESEARCH_TOOL_KINDS,
    ResearchToolContext,
    authorize_atomic_claims,
    build_behavior_subgraph,
    compile_code_facts,
    decompose_atomic_claims,
    propose_evidence_packet,
    read_symbol,
    record_explicit_code_gap,
    search_symbols,
    validate_code_facts,
    validate_evidence_packet,
)
from code2paper.agentic.state_v3 import empty_agent_state_v3
from code2paper.agentic.tool_runtime import atomic_write_bytes, atomic_write_json


_TRAIN_SOURCE = """\
class Trainer:
    def train_loop(self, batches):
        total = 0
        for batch in batches:
            total = total + batch
        return total
"""


def _call(
    *,
    tool_name: str,
    tool_call_id: str,
    snapshot_id: str,
    obligation_id: str = "obl-train-loop",
    arguments: dict[str, Any] | None = None,
    node_budget: int = 64,
) -> ResearchToolCallV1:
    return ResearchToolCallV1(
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        tool_kind=RESEARCH_TOOL_KINDS[tool_name],
        obligation_id=obligation_id,
        goal="Trace the trainer loop from source search to an authorized behavior claim.",
        repo_snapshot_id=snapshot_id,
        arguments=dict(arguments or {}),
        top_k=20,
        node_budget=node_budget,
    )


def evaluate(*, stable_root: Path | None = None) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="code2paper-d1-tool-chain-") as temporary:
        root = Path(temporary)
        (root / "train.py").write_text(_TRAIN_SOURCE, encoding="utf-8")
        snapshot = build_repo_snapshot(root)
        artifact_root = root / ".research-artifacts"

        empty_graph = CodeBehaviorGraphV1(
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
            language="python",
        ).with_digest()
        search_context = ResearchToolContext(
            repo_snapshot=snapshot,
            behavior_graph=empty_graph,
            artifact_root=artifact_root,
        )

        observations = []
        searched = search_symbols(
            search_context,
            _call(
                tool_name="search_symbols",
                tool_call_id="d1-search-trainer",
                snapshot_id=snapshot.snapshot_id,
                arguments={"query": "train_loop"},
            ),
        )
        observations.append(searched)
        if searched.status not in {"success", "truncated"} or not searched.result_refs:
            raise RuntimeError(f"source symbol search failed: {searched.model_dump(mode='json')}")

        symbol_body = searched.result_refs[0].removeprefix("symbol:")
        path, symbol, _line = symbol_body.rsplit(":", 2)
        read = read_symbol(
            search_context,
            _call(
                tool_name="read_symbol",
                tool_call_id="d1-read-trainer",
                snapshot_id=snapshot.snapshot_id,
                arguments={"path": path, "symbol": symbol},
            ),
        )
        observations.append(read)
        built = build_behavior_subgraph(
            search_context,
            _call(
                tool_name="build_behavior_subgraph",
                tool_call_id="d1-build-trainer",
                snapshot_id=snapshot.snapshot_id,
                arguments={"path": path, "symbol": symbol},
            ),
        )
        observations.append(built)
        if read.status != "success" or built.status not in {"success", "truncated"}:
            raise RuntimeError(
                "source read/behavior extraction failed: "
                + repr([item.model_dump(mode="json") for item in (read, built)])
            )

        agenda = ResearchAgendaV1(
            run_id="d1-tool-chain",
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
            items=[ResearchAgendaItemV1(
                obligation_id="obl-train-loop",
                priority="must_cover",
                status="in_progress",
                missing_information=["trainer loop behavior"],
            )],
        )
        runtime = ResearchGraphRuntime(
            run_id="d1-tool-chain",
            repo_snapshot=snapshot,
            agenda=agenda,
            artifact_root=artifact_root,
        )
        state = empty_agent_state_v3(
            run_id=runtime.run_id,
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
        ).to_state_dict()
        state["active_obligation_id"] = "obl-train-loop"
        updated_graph, graph_update = behavior_graph_updater_node(
            state,
            runtime=runtime,
            behavior_graph=empty_graph,
            observations=tuple(observations),
            active_obligation_id="obl-train-loop",
        )
        if not updated_graph.nodes:
            raise RuntimeError("behavior graph update produced no nodes")

        data_context = ResearchToolContext(
            repo_snapshot=snapshot,
            behavior_graph=updated_graph,
            artifact_root=artifact_root,
        )
        candidate = next(
            (
                node for node in updated_graph.nodes
                if node.predicate in {"LOOP", "COMPUTE", "RETURN", "TRANSFORM"}
            ),
            updated_graph.nodes[0],
        )
        packet_id = "packet-d1-train-loop"
        chain_calls = [
            (
                "propose",
                propose_evidence_packet,
                _call(
                    tool_name="propose_evidence_packet",
                    tool_call_id="d1-propose-packet",
                    snapshot_id=snapshot.snapshot_id,
                    arguments={
                        "obligation_tag": "obl-train-loop",
                        "packet_id": packet_id,
                        "scope": symbol,
                        "anchor_span_ids": (candidate.source_span_id,),
                        "behavior_node_ids": (candidate.node_id,),
                        "composition_rationale": "One source-backed behavior node anchors the obligation.",
                    },
                ),
            ),
            (
                "validate_packet",
                validate_evidence_packet,
                _call(
                    tool_name="validate_evidence_packet",
                    tool_call_id="d1-validate-packet",
                    snapshot_id=snapshot.snapshot_id,
                    arguments={"packet_id": packet_id},
                ),
            ),
            (
                "compile_facts",
                compile_code_facts,
                _call(
                    tool_name="compile_code_facts",
                    tool_call_id="d1-compile-facts",
                    snapshot_id=snapshot.snapshot_id,
                    arguments={"packet_id": packet_id},
                ),
            ),
        ]
        chain_observations = []
        for _label, executor, call in chain_calls:
            observation = executor(data_context, call)
            chain_observations.append(observation)
            if observation.status != "success":
                raise RuntimeError(f"{call.tool_name} failed: {observation.model_dump(mode='json')}")

        fact_set = load_code_facts_v1(data_context.artifact_path("fact_sets", packet_id))
        fact_id = fact_set.facts[0].fact_id
        validate_facts = validate_code_facts(
            data_context,
            _call(
                tool_name="validate_code_facts",
                tool_call_id="d1-validate-facts",
                snapshot_id=snapshot.snapshot_id,
                arguments={"fact_id": fact_id, "fact_set_id": packet_id},
            ),
        )
        chain_observations.append(validate_facts)
        if validate_facts.status != "success":
            raise RuntimeError(f"validate_code_facts failed: {validate_facts.model_dump(mode='json')}")

        fact = fact_set.facts[0]
        object_text = ", ".join(fact.object) if isinstance(fact.object, list) else str(fact.object)
        claim_proposal = {
            "claim_id": "claim-d1-train-loop",
            "canonical_text": f"{fact.subject} {fact.predicate} {object_text}".strip(),
            "claim_kind": "implementation_behavior",
            "proposed_fact_ids": [fact.fact_id],
            "covers_obligation_ids": ["obl-train-loop"],
            "required_qualifiers": list(fact.conditions),
            "unsupported_author_fragments": [],
            "allowed_wording_boundary": "exact predicate, operands, and source condition only",
        }
        proposed_claims = decompose_atomic_claims(
            data_context,
            _call(
                tool_name="decompose_atomic_claims",
                tool_call_id="d1-propose-claim",
                snapshot_id=snapshot.snapshot_id,
                arguments={
                    "fact_ids": (fact.fact_id,),
                    "fact_set_id": packet_id,
                    "claim_proposals": (claim_proposal,),
                },
            ),
        )
        chain_observations.append(proposed_claims)
        if proposed_claims.status != "success":
            raise RuntimeError(f"decompose_atomic_claims failed: {proposed_claims.model_dump(mode='json')}")
        proposal_set_id = next(
            note.split("=", 1)[1]
            for note in proposed_claims.diagnostics.notes
            if note.startswith("proposal_set_id=")
        )
        authorized = authorize_atomic_claims(
            data_context,
            _call(
                tool_name="authorize_atomic_claims",
                tool_call_id="d1-authorize-claim",
                snapshot_id=snapshot.snapshot_id,
                arguments={
                    "claim_ids": ("claim-d1-train-loop",),
                    "proposal_set_id": proposal_set_id,
                },
            ),
        )
        chain_observations.append(authorized)
        if authorized.status != "success":
            raise RuntimeError(f"authorize_atomic_claims failed: {authorized.model_dump(mode='json')}")

        # Exercise the negative terminal path on the same fresh snapshot.  A
        # gap must carry a real in-snapshot scope and replay to the same
        # immutable artifact instead of creating a second terminal record.
        gap_call = _call(
            tool_name="record_explicit_code_gap",
            tool_call_id="d1-record-gap",
            snapshot_id=snapshot.snapshot_id,
            obligation_id="obl-gap",
            arguments={
                "obligation_id_ref": "obl-gap",
                "termination_reason": "no executable evidence after bounded search",
                "search_scope": ("train.py",),
                "attempted_tools": ("search_symbols", "read_symbol"),
                "search_complete": True,
            },
        )
        terminal_gap = record_explicit_code_gap(data_context, gap_call)
        terminal_gap_replay = record_explicit_code_gap(data_context, gap_call)
        if terminal_gap.status != "success" or terminal_gap_replay.status != "success":
            raise RuntimeError(
                "terminal gap recording failed: "
                + repr([
                    terminal_gap.model_dump(mode="json"),
                    terminal_gap_replay.model_dump(mode="json"),
                ])
            )

        packet_path = data_context.artifact_path("validated_packets", packet_id)
        claim_set_path = next(
            Path(note.split("=", 1)[1])
            for note in authorized.diagnostics.notes
            if note.startswith("artifact=")
        )
        claim_set = load_atomic_claims_v3(claim_set_path)
        packet = EvidencePacketV3.model_validate_json(packet_path.read_text(encoding="utf-8"))
        packet_span_ids = {
            span.span_id for span in packet.spans
        }
        authorized_claim = claim_set.claims[0]
        trace = [
            {
                "tool_name": observation.tool_name,
                "tool_call_id": observation.tool_call_id,
                "status": observation.status,
                "input_digest": observation.input_digest,
                "output_digest": observation.output_digest,
                "result_refs": list(observation.result_refs),
                "exact_span_ids": list(observation.exact_span_ids),
            }
            for observation in [
                *observations,
                *chain_observations,
                terminal_gap,
                terminal_gap_replay,
            ]
        ]
        terminal_gap_path = data_context.artifact_path("terminal_gaps", "obl-gap")
        terminal_gap_payload = (
            json.loads(terminal_gap_path.read_text(encoding="utf-8"))
            if terminal_gap_path is not None and terminal_gap_path.is_file()
            else {}
        )
        invariants = {
            "source_search_read_success": (
                searched.status in {"success", "truncated"}
                and read.status == "success"
                and built.status in {"success", "truncated"}
            ),
            "behavior_graph_updated_from_observations": bool(
                graph_update.get("behavior_graph_ref")
                and updated_graph.nodes
            ),
            "validated_packet_persisted": bool(packet_path and packet_path.is_file()),
            "validated_fact_persisted": bool(data_context.artifact_path("fact_sets", packet_id)),
            "authorized_claim_persisted": bool(claim_set_path.is_file() and claim_set.claims),
            "generic_producer_exact": all(
                value.producer_version == GENERIC_RESEARCH_PRODUCER_VERSION
                for value in (fact_set, claim_set)
            ),
            "claim_replays_to_fact_and_packet": bool(
                claim_set.claims
                and set(authorized_claim.fact_ids).issubset({fact.fact_id})
                and fact_set.evidence_packet_digest == packet.source_digest
                and claim_set.evidence_packet_digest == packet.source_digest
                and set(fact.direct_span_ids).issubset(packet_span_ids)
                and set(authorized_claim.direct_evidence_ids).issubset(packet_span_ids)
            ),
            "observation_digests_present": all(
                item.input_digest.startswith("sha256:")
                and item.output_digest.startswith("sha256:")
                for item in [
                    *observations,
                    *chain_observations,
                    terminal_gap,
                    terminal_gap_replay,
                ]
            ),
            "terminal_gap_persisted_with_scope": bool(
                terminal_gap_path
                and terminal_gap_path.is_file()
                and terminal_gap_payload.get("terminal") is True
                and terminal_gap_payload.get("search_scope") == ["train.py"]
            ),
            "terminal_gap_replay_idempotent": bool(
                terminal_gap.result_refs == terminal_gap_replay.result_refs
                and "idempotent_replay=true" in terminal_gap_replay.diagnostics.notes
            ),
        }
        stable_source_path: Path | None = None
        stable_packet_path = packet_path
        stable_fact_path = data_context.artifact_path("fact_sets", packet_id)
        stable_claim_path = claim_set_path
        stable_terminal_gap_path = terminal_gap_path
        if stable_root is not None:
            stable_root = stable_root.resolve()
            stable_root.mkdir(parents=True, exist_ok=True)
            for source_path in artifact_root.rglob("*"):
                if not source_path.is_file():
                    continue
                destination = stable_root / source_path.relative_to(artifact_root)
                atomic_write_bytes(destination, source_path.read_bytes())
            stable_source_path = stable_root.parent / "fixture_repo" / "train.py"
            atomic_write_bytes(stable_source_path, _TRAIN_SOURCE.encode("utf-8"))
            stable_packet_path = stable_root / packet_path.relative_to(artifact_root)
            stable_fact_path = stable_root / data_context.artifact_path("fact_sets", packet_id).relative_to(artifact_root)
            stable_claim_path = stable_root / claim_set_path.relative_to(artifact_root)
            stable_terminal_gap_path = stable_root / terminal_gap_path.relative_to(artifact_root)

        return {
            "schema_version": "d1_tool_data_plane_acceptance_v1",
            "status": "passed" if all(invariants.values()) else "failed",
            "snapshot": {
                "repo_snapshot_id": snapshot.snapshot_id,
                "project_tree_hash": snapshot.project_tree_hash,
                "fixture_source": str(stable_source_path or (root / "train.py")),
            },
            "graph": {
                "content_digest": updated_graph.content_digest,
                "node_count": len(updated_graph.nodes),
                "relation_count": len(updated_graph.relations),
                "selected_node_id": candidate.node_id,
            },
            "artifacts": {
                "artifact_root": str(stable_root or artifact_root),
                "validated_packet": str(stable_packet_path),
                "fact_set": str(stable_fact_path),
                "authorized_claim_set": str(stable_claim_path),
                "terminal_gap": str(stable_terminal_gap_path),
            },
            "trace": trace,
            "invariants": invariants,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    stable_root = args.output.resolve().parent / "artifact_store"
    report = evaluate(stable_root=stable_root)
    atomic_write_json(args.output, report)
    if report["status"] != "passed":
        raise SystemExit(1)
    print(report["status"])


if __name__ == "__main__":
    main()
