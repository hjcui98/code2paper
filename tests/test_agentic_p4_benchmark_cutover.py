from __future__ import annotations

from pathlib import Path
import hashlib
import json

from code2paper.agentic.benchmark_v2 import (
    BenchmarkObservationV2,
    ObservedClaim,
    ObservedFigureElement,
    build_benchmark_report_v2,
    evaluate_observation,
    load_benchmark_dataset_v2,
    validate_gold_evidence,
)
from code2paper.agentic.cutover import LegacyTrustContractV1, RolloutEvidenceV2, decide_cutover
from code2paper.agentic.benchmark_observation import (
    BenchmarkRunReviewV2,
    ClaimAdjudicationV2,
    MutationTrialAdjudicationV2,
    extract_benchmark_observation_v2,
)
from code2paper.agentic.benchmark_protocol import build_benchmark_protocol_v2
from code2paper.agentic.adversarial_campaign import run_adversarial_campaign_v2
from code2paper.agentic.legacy_v2_audit import audit_legacy_run_against_gold_v2


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
        default_intent = case.intents[0].intent_id if case.intents else ""
        for variant in ("fixed_legacy", "agentic_deterministic"):
            observation = _perfect_observation(case, variant, intent_id=default_intent)
            runs.append(evaluate_observation(case, observation))
        for intent in case.intents or [None]:
            intent_id = intent.intent_id if intent else ""
            for repeat in (1, 2, 3):
                observation = _perfect_observation(case, "agentic_gemma4_mtp", repeat, intent_id)
                runs.append(evaluate_observation(case, observation))
    return runs


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


def test_cutover_requires_shadow_opt_in_and_canary_before_default() -> None:
    dataset = load_benchmark_dataset_v2(DATASET_PATH)
    runs = _complete_runs(dataset)
    base = RolloutEvidenceV2(
        protocol_validated=True, team_false_block_threshold=0.0,
        legacy_contract_marked=True, migration_guide_complete=True,
    )

    shadow = decide_cutover(dataset, runs, base)
    opt_in = decide_cutover(dataset, runs, base.model_copy(update={"shadow_cases": 4, "shadow_reviewed": True}))
    canary = decide_cutover(dataset, runs, base.model_copy(update={
        "shadow_cases": 4, "shadow_reviewed": True, "opt_in_cases": 4,
    }))
    default = decide_cutover(dataset, runs, base.model_copy(update={
        "shadow_cases": 4, "shadow_reviewed": True, "opt_in_cases": 4, "canary_cases": 4,
    }))

    assert shadow.status == "shadow_ready" and shadow.default_mode == "legacy"
    assert opt_in.status == "opt_in_ready" and opt_in.default_mode == "legacy"
    assert canary.status == "canary_ready" and canary.default_mode == "legacy"
    assert default.status == "default_ready" and default.default_mode == "agentic"


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
        capability_profile_digest="sha256:profile",
    )

    assert len(protocol.specs) == 25
    assert all(item.environment["CODE2PAPER_LLM_CACHE"] == "0" for item in protocol.specs)
    fastgs_training = [item for item in protocol.specs if item.case_id == "fastgs" and item.intent_id == "training_mechanics"]
    assert len({item.repo_snapshot_id for item in fastgs_training}) == 1
    assert {item.repeat_index for item in fastgs_training if item.variant == "agentic_gemma4_mtp"} == {1, 2, 3}


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
        mutation_trials=trial_reviews,
        usable_completion=True,
    )

    observation = extract_benchmark_observation_v2(case, review)

    assert observation.claims[0].trace_exact
    assert observation.detected_mutation_ids == ["TM1", "TM2", "TM3"]
    assert observation.asset_lineage_complete and observation.usable_completion
    assert observation.authoring_revision_loops == 2


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
