"""D3 vertical proof for profile-free holdout and mutation acceptance."""

from __future__ import annotations

from pathlib import Path

from code2paper.agentic.generic_claim_compiler import ClaimProposalV1
from code2paper.agentic.holdout_mutation import (
    HoldoutCaseEvidenceV1,
    MutationSpecV1,
    analyze_python_holdout,
    build_holdout_acceptance_report,
    evaluate_mutation,
    freeze_holdout_protocol,
    materialize_holdout_artifacts,
)


_INLINE = """\
def select_items(scores, k=3):
    probabilities = scores.softmax(dim=-1)
    return probabilities.topk(k)
"""


def _repo(root: Path, name: str, source: str = _INLINE) -> Path:
    path = root / name
    path.mkdir()
    (path / "pipeline.py").write_text(source, encoding="utf-8")
    return path


def _replace(path: Path, old: str, new: str) -> None:
    source = path.read_text(encoding="utf-8")
    assert old in source
    path.write_text(source.replace(old, new), encoding="utf-8")


def test_harness_authorizes_owner_proposal_but_never_synthesizes_claim_prose(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "opaque-a")
    analysis = analyze_python_holdout(repo)
    assert analysis.facts is not None and analysis.facts.facts
    assert analysis.claims is None

    fact = next(item for item in analysis.facts.facts if item.predicate == "selects_top_k")
    proposed = analyze_python_holdout(
        repo,
        claim_proposals=[ClaimProposalV1(
            claim_id="agent-claim-1",
            canonical_text="The selection stage returns the configured top-ranked items.",
            proposed_fact_ids=[fact.fact_id],
            allowed_wording_boundary="returns configured top-ranked items",
        )],
    )
    assert proposed.claims is not None
    assert [item.claim_id for item in proposed.claims.claims] == ["agent-claim-1"]


def test_mutation_harness_preserves_refactors_and_detects_behavior_change(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "opaque-b")
    protocol = freeze_holdout_protocol(repo, author_intent="Describe selection and output.")

    def transform(root: Path, mutation: MutationSpecV1) -> None:
        path = root / "pipeline.py"
        if mutation.mutation_class == "move_file":
            nested = root / "src"
            nested.mkdir()
            path.rename(nested / "engine.py")
        elif mutation.mutation_class == "rename_symbol":
            _replace(path, "select_items", "choose_entries")
        elif mutation.mutation_class == "extract_helper":
            path.write_text(
                "def normalize(values):\n"
                "    return values.softmax(dim=-1)\n\n"
                "def select_items(scores, k=3):\n"
                "    probabilities = normalize(scores)\n"
                "    return probabilities.topk(k)\n",
                encoding="utf-8",
            )
        elif mutation.mutation_class == "inline_helper":
            path.write_text(_INLINE, encoding="utf-8")
        elif mutation.mutation_class == "move_default":
            path.write_text(
                "def select_items(scores, k):\n"
                "    probabilities = scores.softmax(dim=-1)\n"
                "    return probabilities.topk(k)\n\n"
                "def run(scores, k=3):\n"
                "    return select_items(scores, k)\n",
                encoding="utf-8",
            )
        elif mutation.mutation_class == "behavior_change":
            _replace(path, "probabilities.topk(k)", "probabilities.sort(descending=True)")
        else:  # pragma: no cover - the test owns the closed mutation list
            raise AssertionError(mutation.mutation_class)

    outcomes = []
    for mutation_class in ("move_file", "rename_symbol", "extract_helper", "move_default"):
        outcomes.append(evaluate_mutation(
            repo,
            protocol,
            MutationSpecV1(
                mutation_id=f"preserve-{mutation_class}",
                mutation_class=mutation_class,
                target_path="pipeline.py",
                expected_boundary="preserve",
            ),
            transform=transform,
        ))
    extracted_repo = _repo(
        tmp_path,
        "opaque-extracted",
        "def normalize(values):\n"
        "    return values.softmax(dim=-1)\n\n"
        "def select_items(scores, k=3):\n"
        "    probabilities = normalize(scores)\n"
        "    return probabilities.topk(k)\n",
    )
    extracted_protocol = freeze_holdout_protocol(
        extracted_repo,
        author_intent="Describe selection and output.",
    )
    outcomes.append(evaluate_mutation(
        extracted_repo,
        extracted_protocol,
        MutationSpecV1(
            mutation_id="preserve-inline-helper",
            mutation_class="inline_helper",
            target_path="pipeline.py",
            expected_boundary="preserve",
        ),
        transform=transform,
    ))
    outcomes.append(evaluate_mutation(
        repo,
        protocol,
        MutationSpecV1(
            mutation_id="change-selection",
            mutation_class="behavior_change",
            target_path="pipeline.py",
            expected_boundary="change",
        ),
        transform=transform,
    ))
    assert all(item.passed for item in outcomes), [item.model_dump() for item in outcomes]


def test_two_holdout_acceptance_is_fail_closed_and_gap_scoped(tmp_path: Path) -> None:
    repo_a = _repo(tmp_path, "opaque-c")
    repo_b = _repo(tmp_path, "opaque-d", _INLINE.replace("topk(k)", "sum(dim=-1)"))
    protocol_a = freeze_holdout_protocol(repo_a, author_intent="Explain ranked selection.", protocol_id="a")
    protocol_b = freeze_holdout_protocol(repo_b, author_intent="Explain reduction.", protocol_id="b")
    digests = {key: "sha256:" + character * 64 for key, character in zip(
        ("snapshot", "behavior_graph", "evidence_packets", "facts", "claims"), "abcde"
    )}
    cases = [
        HoldoutCaseEvidenceV1(
            case_id="a",
            protocol_digest=protocol_a.content_digest,
            frozen_snapshot_digest=protocol_a.snapshot_digest,
            observed_snapshot_digest=protocol_a.snapshot_digest,
            isolation_passed=True,
            supported_must_cover_mainline_count=1,
            supported_claim_ids=("claim-a",),
            artifact_digests=digests,
        ),
        HoldoutCaseEvidenceV1(
            case_id="b",
            protocol_digest=protocol_b.content_digest,
            frozen_snapshot_digest=protocol_b.snapshot_digest,
            observed_snapshot_digest=protocol_b.snapshot_digest,
            isolation_passed=True,
            supported_must_cover_mainline_count=1,
            supported_claim_ids=("claim-b",),
            artifact_digests=digests,
            incomplete_sections=("training_objective",),
            gap_search_scopes=("*.py",),
            gap_tool_attempts=("search_code", "read_symbol"),
            gap_missing_relations=("objective_calls_loss",),
        ),
    ]
    report = build_holdout_acceptance_report(cases, [])
    assert report.status == "passed"

    failed = build_holdout_acceptance_report([
        cases[0],
        cases[1].model_copy(update={
            "observed_snapshot_digest": "sha256:changed",
            "supported_must_cover_mainline_count": 0,
            "unsupported_positive_sentence_count": 1,
            "gap_missing_relations": (),
        }),
    ], [])
    assert failed.status == "failed"
    assert "case:b:source_changed_after_freeze" in failed.failures
    assert "case:b:no_supported_must_cover_mainline" in failed.failures
    assert "case:b:unsupported_positive_sentences" in failed.failures
    assert "case:b:incomplete_without_precise_gap" in failed.failures


def test_materializer_binds_packets_facts_and_agent_claims(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "opaque-materialized")
    protocol = freeze_holdout_protocol(
        repo,
        author_intent="Describe ranked selection.",
        protocol_id="materialized",
    )
    analysis = analyze_python_holdout(repo)
    assert analysis.facts is not None
    fact = next(item for item in analysis.facts.facts if item.predicate == "selects_top_k")
    case, bundle = materialize_holdout_artifacts(
        analysis,
        protocol=protocol,
        case_id="materialized",
        output_dir=tmp_path / "artifacts",
        claim_proposals=[ClaimProposalV1(
            claim_id="mainline",
            canonical_text="The selection stage returns the configured top-ranked items.",
            proposed_fact_ids=[fact.fact_id],
            allowed_wording_boundary="returns configured top-ranked items",
        )],
        must_cover_claim_ids=["mainline"],
        generation_inputs={
            "protocol_digest": protocol.content_digest,
            "snapshot_digest": protocol.snapshot_digest,
        },
    )
    assert case.isolation_passed
    assert case.supported_must_cover_mainline_count == 1
    assert set(case.artifact_digests) == {
        "snapshot", "behavior_graph", "evidence_packets", "facts", "claims",
    }
    assert bundle.fact_set.evidence_packet_digest == bundle.packet_set.content_digest
    assert bundle.claim_set is not None
    assert bundle.claim_set.evidence_packet_digest == bundle.packet_set.content_digest
    assert (tmp_path / "artifacts" / "evidence_packets_v1.json").exists()
    assert (tmp_path / "artifacts" / "holdout_artifact_manifest_v1.json").exists()
