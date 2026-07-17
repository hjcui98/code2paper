from __future__ import annotations

from pathlib import Path
import hashlib
import json
import pytest
from unittest.mock import patch

from code2paper.agentic.benchmark_v2 import (
    BenchmarkObservationV2,
    ObservedClaim,
    ObservedFigureElement,
    build_benchmark_report_v2,
    evaluate_observation,
    load_benchmark_dataset_v2,
    validate_gold_evidence,
)
from code2paper.agentic.cutover import (
    LegacyTrustContractV1,
    NamedReviewEvidenceV2,
    RolloutEvidenceV2,
    decide_cutover,
)
from code2paper.agentic.benchmark_observation import (
    BenchmarkRunReviewV2,
    ClaimAdjudicationV2,
    FigureAdjudicationV2,
    MutationTrialAdjudicationV2,
    _validated_figure_adjudications,
    build_figure_review_inventory,
    extract_benchmark_observation_v2,
)
from code2paper.agentic.benchmark_protocol import (
    benchmark_spec_digest,
    build_benchmark_protocol_v2,
    validate_protocol_observations_v2,
)
from code2paper.agentic.adversarial_campaign import run_adversarial_campaign_v2
from code2paper.agentic.legacy_v2_audit import audit_legacy_run_against_gold_v2
from code2paper.cli.agentic_benchmark_run import _capability_profile_failure
from code2paper.cli.agentic_benchmark import main as benchmark_main


ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = ROOT / "tests/fixtures/benchmark_v2/gold_adversarial_v1.json"


def _perfect_observation(case, variant: str, repeat: int = 1, intent_id: str = ""):
    intent = next((item for item in case.intents if item.intent_id == intent_id), None)
    claims = [
        ObservedClaim(
            text=claim.text,
            verdict="caveated" if claim.required_qualifiers else "supported",
            gold_claim_id=claim.claim_id,
            direct_evidence_ids=claim.direct_evidence_ids,
            qualifiers_preserved=True,
            trace_exact=True,
            high_risk=claim.high_risk,
        )
        for claim in case.supported_claims
    ]
    figures = [
        ObservedFigureElement(
            element_id=f"N{index}", gold_claim_id=claim.claim_id, semantically_supported=True
        )
        for index, claim in enumerate(case.supported_claims, start=1)
    ]
    return BenchmarkObservationV2(
        case_id=case.case_id,
        variant=variant,
        repeat_index=repeat,
        scope="full_pipeline",
        intent_id=intent_id,
        run_status="success",
        claims=claims,
        figure_elements=figures,
        figure_inventory_expected=len(figures),
        figure_relation_inventory_expected=0,
        figure_inventory_reviewed=True,
        detected_mutation_ids=[item.mutation_id for item in case.mutations],
        stale_trials=2,
        stale_detected=2,
        final_invariant_passed=True,
        completion_complete=True,
        asset_lineage_complete=True,
        usable_completion=True,
        false_block_human_reviewed=True,
        expected_retrieval_targets_observed=intent.expected_retrieval_targets if intent else [],
        section_claim_order=intent.expected_section_claim_order if intent else [item.claim_id for item in case.supported_claims],
        figure_claim_ids=intent.expected_figure_claim_ids if intent else [item.claim_id for item in case.supported_claims],
        support_verdict_signature="stable-supported-set",
        provenance={
            "reviewer": "fixture-human", "reviewed_at": "2026-07-17T00:00:00Z",
            **{f"mutation_trial:{item.mutation_id}": f"sha256:{item.mutation_id}" for item in case.mutations},
        },
    )


def _complete_runs(dataset):
    runs = []
    for case in dataset.cases:
        for intent in case.intents or [None]:
            intent_id = intent.intent_id if intent else ""
            for variant in ("fixed_legacy", "agentic_deterministic"):
                observation = _perfect_observation(case, variant, intent_id=intent_id)
                runs.append(evaluate_observation(case, observation))
            for repeat in (1, 2, 3):
                observation = _perfect_observation(case, "agentic_gemma4_mtp", repeat, intent_id)
                runs.append(evaluate_observation(case, observation))
    return runs


def _validated_reviews(dataset) -> NamedReviewEvidenceV2:
    count = sum((2 + 3) * max(1, len(case.intents)) for case in dataset.cases)
    return NamedReviewEvidenceV2(
        source="digest_pinned_review_artifacts",
        review_artifact_digests=[f"sha256:{index:064x}" for index in range(1, count + 1)],
    )


def test_gold_dataset_has_exact_current_code_evidence_and_required_scope() -> None:
    dataset = load_benchmark_dataset_v2(DATASET_PATH)

    assert validate_gold_evidence(dataset, ROOT) == []
    assert len(dataset.cases) == 4
    assert len([item for item in dataset.cases if item.project_kind == "real"]) == 3
    assert next(item for item in dataset.cases if item.case_id == "fastgs").intents[1].intent_id == "rendering_flow"


def test_observation_metrics_detect_unsupported_paraphrase_and_high_risk_leakage() -> None:
    dataset = load_benchmark_dataset_v2(DATASET_PATH)
    case = next(item for item in dataset.cases if item.case_id == "mos")
    observation = _perfect_observation(case, "agentic_gemma4_mtp")
    observation = observation.model_copy(update={
        "claims": [
            *observation.claims,
            ObservedClaim(
                text="Hard mining closes the modality gap by 12%.", verdict="supported",
                mutation_id="MM1", high_risk=True, trace_exact=False,
            ),
            ObservedClaim(
                text="The epsilon produces a 12% gain.", verdict="supported",
                mutation_id="MM2", high_risk=True, trace_exact=False,
            ),
        ]
    })

    evaluated = evaluate_observation(case, observation)

    assert evaluated.metrics.atomic_claim_semantic_precision < 1.0
    assert evaluated.metrics.unsupported_leakage_rate > 0
    assert evaluated.metrics.paraphrased_unsupported_leakage_rate == 1.0
    assert evaluated.metrics.high_risk_false_supported_rate > 0


def test_completed_observation_cannot_receive_perfect_figure_metrics_from_empty_inventory() -> None:
    dataset = load_benchmark_dataset_v2(DATASET_PATH)
    case = dataset.cases[0]
    observation = _perfect_observation(case, "agentic_gemma4_mtp").model_copy(update={
        "figure_elements": [],
        "figure_inventory_reviewed": False,
    })

    evaluated = evaluate_observation(case, observation)

    assert evaluated.metrics.figure_element_semantic_precision == 0.0
    assert evaluated.metrics.direct_edge_evidence_rate == 0.0
    assert evaluated.metrics.rendered_element_drift_rate == 1.0
    assert "complete_without_full_figure_human_review_inventory" in evaluated.failures


def test_figure_edge_review_requires_explicit_direct_relation_evidence_decision() -> None:
    inventory = build_figure_review_inventory({
        "nodes": [
            {"element_id": "scene-N1", "label": "Source"},
            {"element_id": "scene-N2", "label": "Target"},
        ],
        "edges": [{
            "element_id": "scene-E1", "label": "passes tensor", "relation_id": "R1",
        }],
        "annotations": [],
        "groups": [],
    })
    decisions = [FigureAdjudicationV2(**{
        **item,
        "semantically_supported": True,
        "rendered_drift": False,
    }) for item in inventory]

    with pytest.raises(ValueError, match="figure edge evidence decision missing"):
        _validated_figure_adjudications(decisions, inventory, completion_complete=True)

    decisions[-1] = decisions[-1].model_copy(update={"direct_relation_evidence": True})
    observed = _validated_figure_adjudications(decisions, inventory, completion_complete=True)
    assert len(observed) == 3
    assert observed[-1].element_kind == "edge"
    assert observed[-1].direct_relation_evidence


def test_named_review_schema_rejects_queue_placeholders_and_naive_timestamps() -> None:
    base = {
        "case_id": "toy_train",
        "variant": "fixed_legacy",
        "run_summary_path": "/tmp/run.json",
        "run_summary_digest": "sha256:test",
        "reviewer": "__REQUIRED_NAMED_HUMAN__",
        "reviewed_at": "__REQUIRED_ISO8601__",
    }

    with pytest.raises(ValueError, match="requires reviewer"):
        BenchmarkRunReviewV2.model_validate(base)
    with pytest.raises(ValueError, match="include a timezone"):
        BenchmarkRunReviewV2.model_validate({
            **base,
            "reviewer": "Ada Reviewer",
            "reviewed_at": "2026-07-17T12:00:00",
        })


def test_named_review_cutover_evidence_rejects_self_reported_or_malformed_digests() -> None:
    with pytest.raises(ValueError, match="require digest_pinned"):
        NamedReviewEvidenceV2(source="none", review_artifact_digests=["sha256:" + "a" * 64])
    with pytest.raises(ValueError, match="must be unique"):
        NamedReviewEvidenceV2(
            source="digest_pinned_review_artifacts",
            review_artifact_digests=["sha256:" + "a" * 64, "sha256:" + "a" * 64],
        )
    with pytest.raises(ValueError, match="must be sha256"):
        NamedReviewEvidenceV2(
            source="digest_pinned_review_artifacts",
            review_artifact_digests=["sha256:not-a-real-digest"],
        )


def test_cutover_fails_closed_when_repeats_or_rollout_evidence_are_missing() -> None:
    dataset = load_benchmark_dataset_v2(DATASET_PATH)
    runs = _complete_runs(dataset)
    runs = [item for item in runs if not (
        item.observation.variant == "agentic_gemma4_mtp"
        and item.observation.case_id == "fastgs"
        and item.observation.intent_id == "rendering_flow"
        and item.observation.repeat_index == 3
    )]

    decision = decide_cutover(dataset, runs, RolloutEvidenceV2())

    assert decision.status == "hold"
    assert decision.default_mode == "legacy"
    assert "gemma_repeats_below_three:fastgs:rendering_flow" in decision.failures
    assert "team_false_block_threshold_unset" in decision.failures


def test_cutover_requires_fixed_and_deterministic_runs_for_every_intent() -> None:
    dataset = load_benchmark_dataset_v2(DATASET_PATH)
    runs = [
        item for item in _complete_runs(dataset)
        if not (
            item.observation.case_id == "fastgs"
            and item.observation.variant == "agentic_deterministic"
            and item.observation.intent_id == "rendering_flow"
        )
    ]

    decision = decide_cutover(
        dataset,
        runs,
        RolloutEvidenceV2(protocol_validated=True, team_false_block_threshold=0.0),
    )

    assert "missing_matrix_run:fastgs:agentic_deterministic:rendering_flow:1" in decision.failures
    assert decision.status == "hold"


def test_cutover_rejects_duplicate_or_unexpected_matrix_records() -> None:
    dataset = load_benchmark_dataset_v2(DATASET_PATH)
    runs = _complete_runs(dataset)
    duplicate = runs[0]
    unexpected = runs[1].model_copy(update={
        "observation": runs[1].observation.model_copy(update={"repeat_index": 2}),
    })

    decision = decide_cutover(
        dataset,
        [*runs, duplicate, unexpected],
        RolloutEvidenceV2(protocol_validated=True, team_false_block_threshold=0.0),
    )

    assert "duplicate_matrix_run_identity" in decision.failures
    assert any(item.startswith("unexpected_matrix_run:") for item in decision.failures)
    assert decision.status == "hold"


def test_cutover_requires_shadow_opt_in_and_canary_before_default() -> None:
    dataset = load_benchmark_dataset_v2(DATASET_PATH)
    runs = _complete_runs(dataset)
    base = RolloutEvidenceV2(
        protocol_validated=True, team_false_block_threshold=0.0,
        legacy_contract_marked=True, migration_guide_complete=True,
    )

    reviews = _validated_reviews(dataset)
    shadow = decide_cutover(dataset, runs, base, named_review_evidence=reviews)
    opt_in = decide_cutover(
        dataset, runs, base.model_copy(update={"shadow_cases": 4, "shadow_reviewed": True}),
        named_review_evidence=reviews,
    )
    canary = decide_cutover(dataset, runs, base.model_copy(update={
        "shadow_cases": 4, "shadow_reviewed": True, "opt_in_cases": 4,
    }), named_review_evidence=reviews)
    default = decide_cutover(dataset, runs, base.model_copy(update={
        "shadow_cases": 4, "shadow_reviewed": True, "opt_in_cases": 4, "canary_cases": 4,
    }), named_review_evidence=reviews)

    assert shadow.status == "shadow_ready" and shadow.default_mode == "legacy"
    assert opt_in.status == "opt_in_ready" and opt_in.default_mode == "legacy"
    assert canary.status == "canary_ready" and canary.default_mode == "legacy"
    assert default.status == "default_ready" and default.default_mode == "agentic"


def test_cutover_cannot_authorize_self_reported_observations_without_review_artifacts() -> None:
    dataset = load_benchmark_dataset_v2(DATASET_PATH)
    runs = _complete_runs(dataset)
    rollout = RolloutEvidenceV2(
        protocol_validated=True,
        team_false_block_threshold=0.0,
        shadow_cases=4,
        shadow_reviewed=True,
        opt_in_cases=4,
        canary_cases=4,
        legacy_contract_marked=True,
        migration_guide_complete=True,
    )

    decision = decide_cutover(dataset, runs, rollout)

    assert decision.status == "hold"
    assert decision.default_mode == "legacy"
    assert "digest_pinned_named_review_artifacts_not_validated" in decision.failures


def test_benchmark_cli_observations_input_cannot_emit_authorizing_decision(tmp_path: Path) -> None:
    dataset = load_benchmark_dataset_v2(DATASET_PATH)
    observations_path = tmp_path / "observations.json"
    observations_path.write_text(
        json.dumps([item.observation.model_dump(mode="json") for item in _complete_runs(dataset)]),
        encoding="utf-8",
    )
    rollout_path = tmp_path / "rollout.json"
    rollout_path.write_text(
        RolloutEvidenceV2(
            protocol_validated=True,
            team_false_block_threshold=0.0,
            shadow_cases=4,
            shadow_reviewed=True,
            opt_in_cases=4,
            canary_cases=4,
            legacy_contract_marked=True,
            migration_guide_complete=True,
        ).model_dump_json(),
        encoding="utf-8",
    )
    decision_path = tmp_path / "cutover.json"

    exit_code = benchmark_main([
        "--gold", str(DATASET_PATH),
        "--observations", str(observations_path),
        "--workspace-root", str(ROOT),
        "--rollout", str(rollout_path),
        "--out", str(tmp_path / "report.json"),
        "--cutover-out", str(decision_path),
    ])
    decision = json.loads(decision_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert decision["schema_version"] == "2.1"
    assert decision["status"] == "hold"
    assert decision["default_mode"] == "legacy"
    assert decision["named_review_evidence"]["source"] == "none"
    assert "digest_pinned_named_review_artifacts_not_validated" in decision["failures"]


def test_benchmark_cli_consumes_validated_review_workspace_as_exact_review_source(tmp_path: Path) -> None:
    dataset = load_benchmark_dataset_v2(DATASET_PATH)
    observations = [item.observation for item in _complete_runs(dataset)]
    validated_reviews = []
    for index in range(len(observations)):
        review_path = tmp_path / f"review-{index:02d}.json"
        review_path.write_text(json.dumps({"review": index}), encoding="utf-8")
        validated_reviews.append({"review_path": str(review_path)})
    workspace_report = {
        "status": "passed",
        "hard_gate_passed": True,
        "validated_reviews": validated_reviews,
    }
    rollout_path = tmp_path / "rollout.json"
    rollout_path.write_text(
        RolloutEvidenceV2(team_false_block_threshold=0.0).model_dump_json(),
        encoding="utf-8",
    )
    decision_path = tmp_path / "cutover.json"

    with (
        patch(
            "code2paper.cli.agentic_benchmark.validate_review_workspace",
            return_value=(workspace_report, observations),
        ) as validate_workspace,
        patch("code2paper.cli.agentic_benchmark.load_benchmark_protocol_v2", return_value=object()),
        patch("code2paper.cli.agentic_benchmark.validate_protocol_observations_v2", return_value=[]),
    ):
        exit_code = benchmark_main([
            "--gold", str(DATASET_PATH),
            "--review-workspace", str(tmp_path / "workspace"),
            "--review-queue", str(tmp_path / "queue.json"),
            "--protocol", str(tmp_path / "protocol.json"),
            "--workspace-root", str(ROOT),
            "--rollout", str(rollout_path),
            "--out", str(tmp_path / "report.json"),
            "--cutover-out", str(decision_path),
        ])
    decision = json.loads(decision_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    validate_workspace.assert_called_once()
    assert decision["status"] == "shadow_ready"
    assert decision["named_review_evidence"]["source"] == "digest_pinned_review_artifacts"
    assert len(decision["named_review_evidence"]["review_artifact_digests"]) == 25


def test_benchmark_cli_rejects_pending_review_workspace(tmp_path: Path) -> None:
    with (
        patch(
            "code2paper.cli.agentic_benchmark.validate_review_workspace",
            return_value=({"status": "pending_human_review", "hard_gate_passed": False}, []),
        ),
        patch("code2paper.cli.agentic_benchmark.load_benchmark_protocol_v2", return_value=object()),
    ):
        exit_code = benchmark_main([
            "--gold", str(DATASET_PATH),
            "--review-workspace", str(tmp_path / "workspace"),
            "--review-queue", str(tmp_path / "queue.json"),
            "--protocol", str(tmp_path / "protocol.json"),
            "--workspace-root", str(ROOT),
            "--out", str(tmp_path / "report.json"),
        ])

    assert exit_code == 2
    assert not (tmp_path / "report.json").exists()


def test_cutover_requires_author_intent_adherence_and_paired_organization_change() -> None:
    dataset = load_benchmark_dataset_v2(DATASET_PATH)
    runs = _complete_runs(dataset)
    fastgs_training = next(
        item for item in runs
        if item.observation.case_id == "fastgs"
        and item.observation.variant == "agentic_gemma4_mtp"
        and item.observation.intent_id == "training_mechanics"
        and item.observation.repeat_index == 1
    )
    broken_observation = fastgs_training.observation.model_copy(update={
        "expected_retrieval_targets_observed": [],
        "section_claim_order": ["F2", "F1"],
        "figure_claim_ids": ["F2"],
    })
    replacement = evaluate_observation(
        next(item for item in dataset.cases if item.case_id == "fastgs"),
        broken_observation,
    )
    runs[runs.index(fastgs_training)] = replacement
    rollout = RolloutEvidenceV2(
        protocol_validated=True,
        team_false_block_threshold=0.0,
        legacy_contract_marked=True,
        migration_guide_complete=True,
    )

    decision = decide_cutover(dataset, runs, rollout)

    failures = set(decision.failures)
    assert "hard_threshold_failed:author_intent_adherence" in failures
    assert "paired_intent_organization_unchanged:fastgs:repeat_1" in failures
    assert decision.status == "hold"
    assert decision.default_mode == "legacy"


def test_v2_report_uses_worst_case_and_checks_paired_intent_sensitivity() -> None:
    dataset = load_benchmark_dataset_v2(DATASET_PATH)
    observations = [item.observation for item in _complete_runs(dataset)]

    report = build_benchmark_report_v2(dataset, observations)

    gemma = next(item for item in report.variant_summaries if item.variant == "agentic_gemma4_mtp")
    assert report.case_count == 4
    assert report.real_project_count == 3
    assert report.paired_intent_sensitivity_passed
    assert gemma.worst_case_metrics["unsupported_leakage_rate"] == 0.0
    assert gemma.worst_case_metrics["text_trace_exactness"] == 1.0


def test_legacy_contract_cannot_claim_v2_final_invariant() -> None:
    contract = LegacyTrustContractV1()

    assert contract.contract_version == "legacy-v1-weaker-trust"
    assert not contract.authoritative_v2_final_invariant
    assert "must not" in contract.warning


def test_protocol_freezes_complete_same_snapshot_cache_disabled_matrix(tmp_path: Path) -> None:
    dataset = load_benchmark_dataset_v2(DATASET_PATH)
    authors = {
        ("toy_train", ""): ROOT / "tests/fixtures/toy_train_project_author_markers.yaml",
        ("fastgs", "training_mechanics"): ROOT / "tests/fixtures/benchmark_v2/fastgs_training_intent.yaml",
        ("fastgs", "rendering_flow"): ROOT / "tests/fixtures/benchmark_v2/fastgs_rendering_intent.yaml",
        ("spatial_ssrl", ""): ROOT / "tests/fixtures/benchmark_v2/spatial_ssrl_intent.yaml",
        ("mos", ""): ROOT / "tests/fixtures/benchmark_v2/mos_intent.yaml",
    }

    protocol = build_benchmark_protocol_v2(
        dataset, workspace_root=ROOT, out_root=tmp_path, author_markers=authors,
        code_root=ROOT,
        workspace_commit="abc123", model_id="gemma4-31b-nvfp4",
        llm_base_url="http://127.0.0.1:8000",
        capability_profile_path=ROOT / "tests/baselines/agentic/gemma4_mtp_vllm.profile.json",
        capability_profile_digest="sha256:" + hashlib.sha256(
            (ROOT / "tests/baselines/agentic/gemma4_mtp_vllm.profile.json").read_bytes()
        ).hexdigest(),
    )

    assert len(protocol.specs) == 25
    assert all(item.environment["CODE2PAPER_LLM_CACHE"] == "0" for item in protocol.specs)
    assert all(item.budgets["semantic_verifier_calls"] == 16 for item in protocol.specs)
    assert all(
        item.environment.get("CODE2PAPER_LLM_CAPABILITY_PROFILE") == item.capability_profile_path
        for item in protocol.specs if item.variant != "agentic_deterministic"
    )
    assert all(
        item.environment.get("CODE2PAPER_OPENAI_BASE_URL") == "http://127.0.0.1:8000"
        for item in protocol.specs if item.variant != "agentic_deterministic"
    )
    fastgs_training = [item for item in protocol.specs if item.case_id == "fastgs" and item.intent_id == "training_mechanics"]
    assert len({item.repo_snapshot_id for item in fastgs_training}) == 1
    assert {item.repeat_index for item in fastgs_training if item.variant == "agentic_gemma4_mtp"} == {1, 2, 3}
    model_spec = next(item for item in protocol.specs if item.variant == "agentic_gemma4_mtp")
    assert _capability_profile_failure(model_spec) == ""
    assert _capability_profile_failure(model_spec.model_copy(update={
        "capability_profile_digest": "sha256:stale",
    })) == "capability_profile_drift_before_run"
    assert _capability_profile_failure(model_spec.model_copy(update={
        "environment": {
            **model_spec.environment,
            "CODE2PAPER_OPENAI_BASE_URL": "http://127.0.0.1:9000",
        },
    })) == "llm_base_url_environment_mismatch"

    observations = [item.observation for item in _complete_runs(dataset)]
    for observation, spec in zip(observations, protocol.specs, strict=True):
        observation.provenance["protocol_spec_digest"] = benchmark_spec_digest(spec)
        observation.provenance["repo_snapshot_id"] = spec.repo_snapshot_id
        observation.provenance["model_id"] = spec.model_id
        observation.provenance["capability_profile_digest"] = spec.capability_profile_digest
    failures = validate_protocol_observations_v2(protocol, [*observations, observations[0]])

    assert "observations_contain_duplicate_run_identity" in failures


def test_observation_extraction_is_digest_pinned_and_uses_validator_trace(tmp_path: Path) -> None:
    case = load_benchmark_dataset_v2(DATASET_PATH).cases[0]

    def write(name: str, payload: dict) -> tuple[Path, str]:
        path = tmp_path / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path, "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

    claim_digest = "sha256:claim"
    claims_path, claims_hash = write("claims.json", {"atomic_claims": [{
        "atomic_claim_id": "FAC1", "text": case.supported_claims[0].text, "claim_digest": claim_digest,
    }]})
    validation_path, validation_hash = write("validation.json", {"verdicts": [{
        "atomic_claim_id": "FAC1", "status": "caveated", "direct_evidence_ids": ["E1"],
    }]})
    trace_path, trace_hash = write("trace.json", {"entries": [{
        "atomic_claim_id": "FAC1", "claim_digest": claim_digest, "final_text_span_digest": claim_digest,
        "verdict_status": "caveated", "direct_evidence_ids": ["E1"],
    }]})
    completion_path, completion_hash = write("completion.json", {
        "complete": True, "checks": [
            {"name": "method_figure", "passed": True}, {"name": "traceability", "passed": True},
            {"name": "final_package", "passed": True},
        ],
    })
    evaluation_path, evaluation_hash = write("evaluation.json", {"retrieval_loops": 1, "revision_loops": 2})
    freshness_path, freshness_hash = write("freshness.json", {"passed": True})
    repo_path, repo_hash = write("repo.json", {"snapshot_id": "repo:test"})
    scene = {
        "nodes": [{
            "element_id": "scene-N1",
            "stage_id": "S1",
            "label": "Reviewed stage",
            "kind": "stage",
            "claim_ids": ["T1"],
            "direct_evidence_ids": ["E1"],
            "visible_text_boundary": "Reviewed stage",
        }],
        "edges": [],
        "annotations": [],
        "groups": [],
    }
    scene_path, scene_hash = write("scene.json", scene)
    post_render_path, post_render_hash = write("post-render.json", {"hard_gate_passed": True})
    svg_path = tmp_path / "method.svg"
    svg_path.write_text("<svg><text>Reviewed stage</text></svg>", encoding="utf-8")
    svg_hash = "sha256:" + hashlib.sha256(svg_path.read_bytes()).hexdigest()
    trial_reviews = []
    for mutation in case.mutations:
        path, digest = write(f"{mutation.mutation_id}.json", {"detected": True})
        trial_reviews.append(MutationTrialAdjudicationV2(
            mutation_id=mutation.mutation_id, detected=True,
            trial_artifact_path=str(path), trial_artifact_digest=digest,
        ))
    summary = {
        "status": "success", "blocked_reason": "", "invariant_audit_passed": True,
        "artifacts": {
            "final_text_claims": {"path": str(claims_path), "hash": claims_hash},
            "text_evidence_validation": {"path": str(validation_path), "hash": validation_hash},
            "final_text_trace": {"path": str(trace_path), "hash": trace_hash},
            "agentic_run_completion_report": {"path": str(completion_path), "hash": completion_hash},
            "agentic_run_evaluation_report": {"path": str(evaluation_path), "hash": evaluation_hash},
            "artifact_freshness": {"path": str(freshness_path), "hash": freshness_hash},
            "repo_snapshot": {"path": str(repo_path), "hash": repo_hash},
            "figure_scene": {"path": str(scene_path), "hash": scene_hash},
            "post_render_audit": {"path": str(post_render_path), "hash": post_render_hash},
            "method_overview_svg": {"path": str(svg_path), "hash": svg_hash},
        },
    }
    summary_path, summary_hash = write("summary.json", summary)
    review = BenchmarkRunReviewV2(
        case_id=case.case_id, variant="agentic_deterministic",
        run_summary_path=str(summary_path), run_summary_digest=summary_hash,
        reviewer="human-reviewer", reviewed_at="2026-07-17T00:00:00Z",
        claims=[ClaimAdjudicationV2(
            atomic_claim_id="FAC1", verdict="caveated", gold_claim_id="T1",
            qualifiers_preserved=True,
        )],
        figures=[FigureAdjudicationV2(**{
            **build_figure_review_inventory(scene)[0],
            "gold_claim_id": "T1",
            "semantically_supported": True,
            "rendered_drift": False,
        })],
        mutation_trials=trial_reviews,
        usable_completion=True,
    )

    observation = extract_benchmark_observation_v2(case, review)

    assert observation.claims[0].trace_exact
    assert observation.detected_mutation_ids == ["TM1", "TM2", "TM3"]
    assert observation.asset_lineage_complete and observation.usable_completion
    assert observation.authoring_revision_loops == 2
    assert observation.figure_inventory_reviewed
    assert observation.figure_inventory_expected == 1
    with pytest.raises(ValueError, match="figure review inventory mismatch"):
        extract_benchmark_observation_v2(case, review.model_copy(update={"figures": []}))


def test_cutover_holds_if_agentic_usable_completion_is_below_legacy() -> None:
    dataset = load_benchmark_dataset_v2(DATASET_PATH)
    runs = _complete_runs(dataset)
    degraded = []
    for item in runs:
        if item.observation.variant.startswith("agentic_"):
            observation = item.observation.model_copy(update={"usable_completion": False})
            degraded.append(evaluate_observation(next(case for case in dataset.cases if case.case_id == observation.case_id), observation))
        else:
            degraded.append(item)

    decision = decide_cutover(
        dataset, degraded,
        RolloutEvidenceV2(
            protocol_validated=True, team_false_block_threshold=0.0,
            legacy_contract_marked=True, migration_guide_complete=True,
        ),
    )

    assert "agentic_usable_completion_below_legacy_requires_false_success_evidence" in decision.failures


def test_curated_adversarial_campaign_executes_every_mutation(tmp_path: Path) -> None:
    dataset = load_benchmark_dataset_v2(DATASET_PATH)
    total = 0
    for case in dataset.cases:
        paths = run_adversarial_campaign_v2(case, workspace_root=ROOT, out_root=tmp_path / case.case_id)
        payloads = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
        assert len(paths) == len(case.mutations)
        assert all(item["detected"] for item in payloads)
        total += len(paths)

    assert total == 13


def test_legacy_v2_audit_marks_v1_fidelity_success_as_review_candidate(tmp_path: Path) -> None:
    case = load_benchmark_dataset_v2(DATASET_PATH).cases[0]
    legacy = tmp_path / "legacy"
    method = legacy / "paper/method"
    figure = legacy / "paper/figures/method_overview"
    method.mkdir(parents=True)
    figure.mkdir(parents=True)
    (method / "code2paper_run_report.json").write_text('{"fidelity_passed":true}', encoding="utf-8")
    (method / "method_draft.md").write_text(
        "# Method\nThe module implements a complete production training system.\n", encoding="utf-8",
    )
    (figure / "method_overview.svg").write_text("<svg></svg>", encoding="utf-8")

    report = audit_legacy_run_against_gold_v2(
        case, workspace_root=ROOT, legacy_out_root=legacy, scratch_root=tmp_path / "scratch",
    )

    assert report.legacy_fidelity_passed
    assert not report.text_v2_gate_passed
    assert report.legacy_false_success_candidate
    assert report.requires_named_human_review
