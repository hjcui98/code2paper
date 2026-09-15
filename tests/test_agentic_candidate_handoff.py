"""Project-neutral tests for the bounded Research -> Candidate handoff."""

from __future__ import annotations

import io
import importlib
import json
import signal
from pathlib import Path

import pytest

import code2paper.agentic.autonomous_method_agent as autonomous_method_agent
import code2paper.cli.agentic_run as agentic_run
import code2paper.agentic.publication_method_writer as publication_method_writer
unified_cli = importlib.import_module("code2paper.cli.main")
from code2paper.agentic.evidence_compiler_v3 import AtomicClaimV3
from code2paper.llm.section_writer import WriterSectionInput, _llm_visible_section_payload
from code2paper.agentic.research_models import ResearchAgendaItemV1
from code2paper.agentic.research_promotion import ObservationPromotionRecordV1
from code2paper.agentic.research_terminal import (
    CandidateHandoffV1,
    build_candidate_handoff,
    build_research_closure_admission,
    evaluate_obligation_terminal_proof,
)
from code2paper.schemas import LLMConfig, LLMProvider


def _partial_item(obligation_id: str = "core-partial") -> ResearchAgendaItemV1:
    return ResearchAgendaItemV1(
        obligation_id=obligation_id,
        priority="must_cover",
        status="partial",
        supported_claim_ids=["claim-supported"],
        missing_information=["call_relation:callee output"],
        attempted_actions=["READ_CANDIDATE"],
    )


def _claim(claim_id: str, obligation_id: str) -> AtomicClaimV3:
    return AtomicClaimV3(
        claim_id=claim_id,
        canonical_text=f"Observed implementation for {obligation_id}.",
        fact_ids=[f"fact:{claim_id}"],
        covers_obligation_ids=[obligation_id],
        direct_evidence_ids=[f"span:{claim_id}"],
        required_qualifiers=["only the observed repository fragment"],
        allowed_wording_boundary="Only the observed repository fragment may be stated.",
        canonical_identity=f"identity:{claim_id}",
    )


def _promotion(claim_id: str, obligation_id: str) -> ObservationPromotionRecordV1:
    return ObservationPromotionRecordV1(
        observation_id=f"observation:{claim_id}",
        obligation_id=obligation_id,
        tool_name="read_symbol",
        status="claim_promoted",
        behavior_node_ids=(f"node:{claim_id}",),
        packet_ids=(f"packet:{claim_id}",),
        fact_ids=(f"fact:{claim_id}",),
        claim_ids=(claim_id,),
    )


def _handoff_inputs(obligation_id: str, claim_id: str) -> tuple[tuple[AtomicClaimV3, ...], tuple[ObservationPromotionRecordV1, ...]]:
    return (_claim(claim_id, obligation_id),), (_promotion(claim_id, obligation_id),)


def test_partial_requires_one_post_partial_retry_and_keeps_strict_proof_open() -> None:
    item = _partial_item()
    claims, promotions = _handoff_inputs(item.obligation_id, "claim-supported")
    before_retry = build_candidate_handoff(
        run_id="run-candidate",
        repo_snapshot_id="repo:snapshot",
        project_tree_hash="sha256:tree",
        agenda_items=[item],
        promotion_records=promotions,
        compiled_claim_ids_by_obligation={item.obligation_id: ("claim-supported",)},
        compiled_claims_by_obligation={item.obligation_id: claims},
        post_partial_retry_counts={},
    )
    assert before_retry.eligible is False
    assert "candidate_partial_retry_missing:core-partial" in before_retry.eligibility_reasons

    after_retry = build_candidate_handoff(
        run_id="run-candidate",
        repo_snapshot_id="repo:snapshot",
        project_tree_hash="sha256:tree",
        agenda_items=[item],
        promotion_records=promotions,
        compiled_claim_ids_by_obligation={item.obligation_id: ("claim-supported",)},
        compiled_claims_by_obligation={item.obligation_id: claims},
        post_partial_retry_counts={item.obligation_id: 1},
        retry_gain_by_obligation={item.obligation_id: False},
    )
    assert after_retry.eligible is True
    assert after_retry.partial_obligation_ids == (item.obligation_id,)
    assert after_retry.partial_obligations[0].missing_fields == (
        "call_relation:callee output",
    )
    assert after_retry.partial_obligations[0].semantic_gain_on_retry is False
    assert not evaluate_obligation_terminal_proof(
        item,
        promoted_claim_ids=("claim-supported",),
    ).terminal


def test_partial_without_explicit_qualifier_stays_ineligible() -> None:
    item = _partial_item()
    claims, promotions = _handoff_inputs(item.obligation_id, "claim-supported")
    claims = (claims[0].model_copy(update={
        "required_qualifiers": [],
        "allowed_wording_boundary": "",
    }),)
    handoff = build_candidate_handoff(
        run_id="run-candidate",
        repo_snapshot_id="repo:snapshot",
        project_tree_hash="sha256:tree",
        agenda_items=[item],
        promotion_records=promotions,
        compiled_claims_by_obligation={item.obligation_id: claims},
        post_partial_retry_counts={item.obligation_id: 1},
        retry_gain_by_obligation={item.obligation_id: False},
    )
    assert handoff.eligible is False
    assert "candidate_partial_qualifier_unresolved:core-partial" in (
        handoff.eligibility_reasons
    )
    assert "candidate_partial_qualifier_missing:core-partial" in (
        handoff.eligibility_reasons
    )


def test_partial_without_wording_boundary_stays_ineligible() -> None:
    item = _partial_item()
    claims, promotions = _handoff_inputs(item.obligation_id, "claim-supported")
    claims = (claims[0].model_copy(update={"allowed_wording_boundary": ""}),)
    handoff = build_candidate_handoff(
        run_id="run-candidate",
        repo_snapshot_id="repo:snapshot",
        project_tree_hash="sha256:tree",
        agenda_items=[item],
        promotion_records=promotions,
        compiled_claims_by_obligation={item.obligation_id: claims},
        post_partial_retry_counts={item.obligation_id: 1},
        retry_gain_by_obligation={item.obligation_id: False},
    )
    assert handoff.eligible is False
    assert "candidate_partial_wording_boundary_missing:core-partial" in (
        handoff.eligibility_reasons
    )


def test_candidate_partial_model_requires_both_qualifier_contract_fields() -> None:
    item = _partial_item()
    claims, promotions = _handoff_inputs(item.obligation_id, "claim-supported")
    handoff = build_candidate_handoff(
        run_id="run-candidate",
        repo_snapshot_id="repo:snapshot",
        project_tree_hash="sha256:tree",
        agenda_items=[item],
        promotion_records=promotions,
        compiled_claims_by_obligation={item.obligation_id: claims},
        post_partial_retry_counts={item.obligation_id: 1},
    )
    payload = handoff.model_dump(mode="json")
    payload["partial_obligations"][0]["qualifier"] = ""
    with pytest.raises(ValueError, match="explicit qualifier"):
        CandidateHandoffV1.model_validate(payload)

    payload = handoff.model_dump(mode="json")
    payload["partial_obligations"][0]["allowed_wording_boundary"] = ""
    with pytest.raises(ValueError, match="allowed wording boundary"):
        CandidateHandoffV1.model_validate(payload)


def test_candidate_handoff_id_is_recomputed_from_the_frozen_payload() -> None:
    item = _partial_item()
    claims, promotions = _handoff_inputs(item.obligation_id, "claim-supported")
    handoff = build_candidate_handoff(
        run_id="run-candidate",
        repo_snapshot_id="repo:snapshot",
        project_tree_hash="sha256:tree",
        agenda_items=[item],
        promotion_records=promotions,
        compiled_claims_by_obligation={item.obligation_id: claims},
        post_partial_retry_counts={item.obligation_id: 1},
    )
    payload = handoff.model_dump(mode="json")
    payload["handoff_id"] = "sha256:tampered"
    with pytest.raises(ValueError, match="handoff_id mismatch"):
        CandidateHandoffV1.model_validate(payload)


def test_candidate_defers_non_core_work_and_rejects_structural_failures() -> None:
    core = ResearchAgendaItemV1(
        obligation_id="core-supported",
        priority="must_cover",
        status="supported",
        supported_claim_ids=["claim-core"],
        attempted_actions=["READ_CANDIDATE"],
    )
    deferred = ResearchAgendaItemV1(
        obligation_id="optional-later",
        priority="should_cover",
        status="pending",
    )
    core_claims, core_promotions = _handoff_inputs(core.obligation_id, "claim-core")
    handoff = build_candidate_handoff(
        run_id="run-candidate",
        repo_snapshot_id="repo:snapshot",
        project_tree_hash="sha256:tree",
        agenda_items=[core, deferred],
        promotion_records=core_promotions,
        compiled_claim_ids_by_obligation={core.obligation_id: ("claim-core",)},
        compiled_claims_by_obligation={core.obligation_id: core_claims},
    )
    assert handoff.eligible is True
    assert handoff.deferred_obligation_ids == ("optional-later",)
    assert "candidate_deferred:optional-later" in handoff.warning_codes

    blocked = build_candidate_handoff(
        run_id="run-candidate",
        repo_snapshot_id="repo:snapshot",
        project_tree_hash="sha256:tree",
        agenda_items=[core],
        promotion_records=core_promotions,
        compiled_claim_ids_by_obligation={core.obligation_id: ("claim-core",)},
        compiled_claims_by_obligation={core.obligation_id: core_claims},
        structural_failure_codes=("ownership_ambiguous",),
    )
    assert blocked.eligible is False
    assert "candidate_structural_failure:ownership_ambiguous" in blocked.eligibility_reasons


def test_failed_strict_admission_can_allow_candidate_only_with_handoff() -> None:
    strict_admission = build_research_closure_admission(
        run_id="run-candidate",
        repo_snapshot_id="repo:snapshot",
        project_tree_hash="sha256:tree",
        research_status="incomplete",
        failure_codes=("research_status:incomplete",),
    )
    assert strict_admission.model_calls_allowed is False

    admission = build_research_closure_admission(
        run_id="run-candidate",
        repo_snapshot_id="repo:snapshot",
        project_tree_hash="sha256:tree",
        research_status="incomplete",
        failure_codes=("research_status:incomplete",),
        candidate_handoff_allowed=True,
        candidate_handoff_id="handoff:one",
        candidate_warning_codes=("candidate_partial_unresolved:core-partial",),
        downstream_phases_planned=("planning", "formalizer", "writer"),
    )
    assert admission.model_calls_allowed is True
    assert admission.candidate_handoff_allowed is True
    assert admission.failure_codes == ("research_status:incomplete",)


def test_candidate_lane_removes_only_authenticated_partial_terminal_failure() -> None:
    item = _partial_item()
    claims, promotions = _handoff_inputs(item.obligation_id, "claim-supported")
    handoff = build_candidate_handoff(
        run_id="run-candidate",
        repo_snapshot_id="repo:snapshot",
        project_tree_hash="sha256:tree",
        agenda_items=[item],
        promotion_records=promotions,
        compiled_claim_ids_by_obligation={item.obligation_id: ("claim-supported",)},
        compiled_claims_by_obligation={item.obligation_id: claims},
        post_partial_retry_counts={item.obligation_id: 1},
    )
    failures = publication_method_writer._candidate_lane_research_failures(
        (
            "unified_core_intent_partial_without_terminal_gap:core-partial",
            "unified_research_snapshot_mismatch",
        ),
        candidate_handoff=handoff,
    )
    assert failures == ("unified_research_snapshot_mismatch",)


def test_partial_handoff_is_visible_to_writer_as_non_assertive_context() -> None:
    section = WriterSectionInput(
        section_id="section-one",
        heading="Method",
        prompt_payload={
            "section_id": "section-one",
            "heading": "Method",
            "shared_contexts": ["{}"],
            "candidate_partial_handoff": [{
                "obligation_id": "core-partial",
                "missing_fields": ["call_relation:callee output"],
                "writer_instruction": "Treat missing fields as uncertainty.",
            }],
        },
    )
    visible = _llm_visible_section_payload(section)
    assert visible["candidate_partial_handoff"][0]["missing_fields"] == [
        "call_relation:callee output",
    ]


def test_product_runner_persists_partial_summary_when_research_raises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture_repo = Path(__file__).resolve().parent / "fixtures" / "research_loop_project"

    def fail_before_graph_returns(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("synthetic research fault")

    monkeypatch.setattr(
        autonomous_method_agent,
        "run_product_research_phase",
        fail_before_graph_returns,
    )
    out_root = tmp_path / "interrupted"
    with pytest.raises(RuntimeError, match="synthetic research fault"):
        autonomous_method_agent.run_autonomous_method_agent(
            repo_path=fixture_repo,
            out_root=out_root,
            llm_config=LLMConfig(provider=LLMProvider.NONE),
            write_method_text=False,
            run_id="run-interrupted",
            max_research_turns=2,
        )

    partial_path = out_root / "artifacts" / "research_product" / "run_summary.partial.json"
    terminal_path = out_root / "artifacts" / "06_authoring" / "invocations" / "run_terminal_event.json"
    assert partial_path.is_file()
    assert terminal_path.is_file()
    partial = json.loads(partial_path.read_text(encoding="utf-8"))
    terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
    assert partial["run_id"] == "run-interrupted"
    assert partial["exception_type"] == "RuntimeError"
    assert terminal["terminal_reason"] == "exception"


def test_product_finalizer_binds_attempt_id_to_partial_and_terminal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture_repo = Path(__file__).resolve().parent / "fixtures" / "research_loop_project"
    attempt_id = "attempt-worker-exception"
    monkeypatch.setenv("CODE2PAPER_METHOD_AGENT_ATTEMPT_ID", attempt_id)

    def fail_impl(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("synthetic worker exception")

    monkeypatch.setattr(
        autonomous_method_agent,
        "_run_autonomous_method_agent_impl",
        fail_impl,
    )
    out_root = tmp_path / "worker-attempt"
    with pytest.raises(RuntimeError, match="synthetic worker exception"):
        autonomous_method_agent.run_autonomous_method_agent(
            repo_path=fixture_repo,
            out_root=out_root,
            llm_config=LLMConfig(provider=LLMProvider.NONE),
            write_method_text=False,
            run_id="run-worker-attempt",
            max_research_turns=2,
        )

    partial_path = (
        out_root / "artifacts" / "research_product" / "run_summary.partial.json"
    )
    terminal_path = (
        out_root / "artifacts" / "06_authoring" / "invocations"
        / f"run_terminal_event.{attempt_id}.json"
    )
    assert partial_path.is_file()
    assert terminal_path.is_file()
    partial = json.loads(partial_path.read_text(encoding="utf-8"))
    terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
    assert partial["attempt_id"] == attempt_id
    assert terminal["extra"]["attempt_id"] == attempt_id
    assert terminal["terminal_reason"] == "exception"
    assert terminal["extra"]["exit_type"] == "exception"

    state = agentic_run._worker_attempt_artifact_state(out_root, attempt_id)
    assert state["partial_valid"] is True
    assert state["terminal_valid"] is True
    assert state["terminal_reason"] == "exception"
    assert state["exit_type"] == "exception"


def test_supervisor_preserves_real_worker_exception_finalizer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture_repo = Path(__file__).resolve().parent / "fixtures" / "research_loop_project"
    out_root = tmp_path / "supervised-worker-exception"
    captured: dict[str, str] = {}

    def fail_impl(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("synthetic worker exception")

    monkeypatch.setattr(
        autonomous_method_agent,
        "_run_autonomous_method_agent_impl",
        fail_impl,
    )

    class _WorkerThatFinalizesInProcess:
        pid = 91238

        def __init__(self, *args: object, **kwargs: object) -> None:
            env = kwargs["env"]
            attempt_id = str(env["CODE2PAPER_METHOD_AGENT_ATTEMPT_ID"])
            captured["attempt_id"] = attempt_id
            monkeypatch.setenv("CODE2PAPER_METHOD_AGENT_ATTEMPT_ID", attempt_id)
            self.returncode = 2
            self.stdout = io.BytesIO()
            self.stderr = io.BytesIO()
            try:
                autonomous_method_agent.run_autonomous_method_agent(
                    repo_path=fixture_repo,
                    out_root=out_root,
                    llm_config=LLMConfig(provider=LLMProvider.NONE),
                    write_method_text=False,
                    run_id="run-supervised-worker-exception",
                    max_research_turns=2,
                )
            except RuntimeError:
                pass

        def poll(self) -> int:
            return self.returncode

        def wait(self, timeout: float | None = None) -> int:
            return self.returncode

        def terminate(self) -> None:
            return None

        def kill(self) -> None:
            return None

    monkeypatch.setattr(agentic_run.subprocess, "Popen", _WorkerThatFinalizesInProcess)
    code = agentic_run.supervised_method_agent_main([
        "run",
        "--repo", str(fixture_repo),
        "--out", str(out_root),
        "--no-live-llm",
        "--run-id", "run-supervised-worker-exception",
    ])
    assert code == 2
    attempt_id = captured["attempt_id"]
    invocation_root = out_root / "artifacts" / "06_authoring" / "invocations"
    assert not (
        invocation_root / f"run_terminal_event.supervisor.{attempt_id}.json"
    ).exists()
    supervisor = json.loads(
        (invocation_root / f"run_supervisor_event.{attempt_id}.json")
        .read_text(encoding="utf-8")
    )
    assert supervisor["worker_partial_valid"] is True
    assert supervisor["worker_terminal_valid"] is True
    assert supervisor["worker_terminal_reason"] == "exception"
    assert supervisor["worker_exit_type"] == "exception"
    assert supervisor["primary_terminal_source"] == "worker"
    assert supervisor["fallback_artifacts"] == {}
    assert supervisor["parent_stop_signal"] is None

    worker_terminal = json.loads(
        (invocation_root / f"run_terminal_event.{attempt_id}.json")
        .read_text(encoding="utf-8")
    )
    assert worker_terminal["terminal_reason"] == "exception"

    process = json.loads(
        (out_root / "method_agent_process.json").read_text(encoding="utf-8")
    )
    assert process["primary_terminal_source"] == "worker"
    assert process["worker_terminal_reason"] == "exception"
    assert process["worker_exit_type"] == "exception"
    assert process["parent_stop_signal"] is None


def test_supervisor_records_parent_observed_sigkill_without_reusing_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _KilledWorker:
        pid = 91234

        def __init__(self) -> None:
            self.stdout = io.BytesIO()
            self.stderr = io.BytesIO()

        def poll(self) -> int:
            return -signal.SIGKILL

        def wait(self, timeout: float | None = None) -> int:
            return -signal.SIGKILL

        def terminate(self) -> None:
            return None

        def kill(self) -> None:
            return None

    monkeypatch.setattr(agentic_run.subprocess, "Popen", lambda *args, **kwargs: _KilledWorker())
    out_root = tmp_path / "supervised"
    code = agentic_run.supervised_method_agent_main([
        "run",
        "--repo", str(Path(__file__).resolve().parent / "fixtures" / "research_loop_project"),
        "--out", str(out_root),
        "--no-live-llm",
        "--run-id", "run-sigkill",
    ])
    assert code == 128 + signal.SIGKILL
    attempts = tuple((out_root / "method_agent_attempts").glob("*.json"))
    assert len(attempts) == 1
    attempt = json.loads(attempts[0].read_text(encoding="utf-8"))
    assert attempt["status"] == "external_termination"
    assert attempt["worker_returncode"] == -signal.SIGKILL
    partial = out_root / "artifacts" / "research_product" / "run_summary.partial.json"
    assert partial.is_file()
    terminal = out_root / "artifacts" / "06_authoring" / "invocations" / (
        f"run_terminal_event.supervisor.{attempts[0].stem}.json"
    )
    assert terminal.is_file()
    supervisor_event = out_root / "artifacts" / "06_authoring" / "invocations" / (
        f"run_supervisor_event.{attempts[0].stem}.json"
    )
    assert supervisor_event.is_file()
    assert not (out_root / "run_stdout.log").exists()
    assert (out_root / f"run_stdout.{attempts[0].stem}.log").is_file()


def test_supervisor_preserves_worker_exception_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out_root = tmp_path / "worker-exception"

    class _FailedWorker:
        pid = 91235

        def __init__(self, *args: object, **kwargs: object) -> None:
            self.stdout = io.BytesIO()
            self.stderr = io.BytesIO()
            env = kwargs["env"]
            attempt_id = str(env["CODE2PAPER_METHOD_AGENT_ATTEMPT_ID"])
            partial = out_root / "artifacts" / "research_product" / "run_summary.partial.json"
            partial.parent.mkdir(parents=True, exist_ok=True)
            partial.write_text(json.dumps({
                "schema_version": "1.0",
                "run_id": "run-exception",
                "attempt_id": attempt_id,
                "status": "interrupted",
                "terminal_reason": "exception",
                "exception_type": "RuntimeError",
                "exception_message": "worker-owned diagnostic",
            }), encoding="utf-8")
            terminal = (
                out_root / "artifacts" / "06_authoring" / "invocations"
                / f"run_terminal_event.{attempt_id}.json"
            )
            terminal.parent.mkdir(parents=True, exist_ok=True)
            terminal.write_text(json.dumps({
                "terminal_reason": "exception",
                "extra": {"attempt_id": attempt_id},
            }), encoding="utf-8")

        def poll(self) -> int:
            return 2

        def wait(self, timeout: float | None = None) -> int:
            return 2

        def terminate(self) -> None:
            return None

        def kill(self) -> None:
            return None

    monkeypatch.setattr(agentic_run.subprocess, "Popen", _FailedWorker)
    code = agentic_run.supervised_method_agent_main([
        "run",
        "--repo", str(Path(__file__).resolve().parent / "fixtures" / "research_loop_project"),
        "--out", str(out_root),
        "--no-live-llm",
        "--run-id", "run-exception",
    ])
    assert code == 2
    partial = json.loads(
        (out_root / "artifacts" / "research_product" / "run_summary.partial.json")
        .read_text(encoding="utf-8")
    )
    assert partial["exception_type"] == "RuntimeError"
    attempts = tuple((out_root / "method_agent_attempts").glob("*.json"))
    assert len(attempts) == 1
    attempt_id = attempts[0].stem
    terminal = json.loads(
        (out_root / "artifacts" / "06_authoring" / "invocations"
         / f"run_terminal_event.{attempt_id}.json").read_text(encoding="utf-8")
    )
    assert terminal["terminal_reason"] == "exception"
    supervisor = json.loads(
        (out_root / "artifacts" / "06_authoring" / "invocations"
         / f"run_supervisor_event.{attempt_id}.json").read_text(encoding="utf-8")
    )
    assert supervisor["worker_partial_valid"] is True
    assert supervisor["worker_terminal_valid"] is True
    assert supervisor["worker_terminal_reason"] == "exception"
    assert supervisor["primary_terminal_source"] == "worker"
    assert supervisor["fallback_artifacts"] == {}
    assert "run_terminal_event" not in json.loads(
        attempts[0].read_text(encoding="utf-8")
    ).get("partial_artifacts", {})


@pytest.mark.parametrize("returncode", [-signal.SIGTERM])
def test_supervisor_fallback_closes_parent_observed_sigterm(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    returncode: int,
) -> None:
    class _SignaledWorker:
        pid = 91236

        def __init__(self) -> None:
            self.stdout = io.BytesIO()
            self.stderr = io.BytesIO()

        def poll(self) -> int:
            return returncode

        def wait(self, timeout: float | None = None) -> int:
            return returncode

        def terminate(self) -> None:
            return None

        def kill(self) -> None:
            return None

    monkeypatch.setattr(agentic_run.subprocess, "Popen", lambda *args, **kwargs: _SignaledWorker())
    out_root = tmp_path / "sigterm"
    code = agentic_run.supervised_method_agent_main([
        "run",
        "--repo", str(Path(__file__).resolve().parent / "fixtures" / "research_loop_project"),
        "--out", str(out_root),
        "--no-live-llm",
    ])
    assert code == 128 + signal.SIGTERM
    attempts = tuple((out_root / "method_agent_attempts").glob("*.json"))
    assert len(attempts) == 1
    attempt_id = attempts[0].stem
    assert (
        out_root / "artifacts" / "06_authoring" / "invocations"
        / f"run_terminal_event.supervisor.{attempt_id}.json"
    ).is_file()
    assert (
        out_root / "artifacts" / "06_authoring" / "invocations"
        / f"run_supervisor_event.{attempt_id}.json"
    ).is_file()


def test_supervisor_routes_sigint_through_the_same_finalizer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _InterruptingWorker:
        pid = 91237

        def __init__(self) -> None:
            self.stdout = io.BytesIO()
            self.stderr = io.BytesIO()
            self.alive = True
            self.returncode = -signal.SIGTERM

        def poll(self) -> int | None:
            return None if self.alive else self.returncode

        def wait(self, timeout: float | None = None) -> int:
            os.kill(os.getpid(), signal.SIGINT)
            return self.returncode

        def terminate(self) -> None:
            self.alive = False

        def kill(self) -> None:
            self.alive = False

    import os

    monkeypatch.setattr(
        agentic_run.subprocess,
        "Popen",
        lambda *args, **kwargs: _InterruptingWorker(),
    )
    out_root = tmp_path / "sigint"
    code = agentic_run.supervised_method_agent_main([
        "run",
        "--repo", str(Path(__file__).resolve().parent / "fixtures" / "research_loop_project"),
        "--out", str(out_root),
        "--no-live-llm",
    ])
    assert code == 128 + signal.SIGINT
    attempts = tuple((out_root / "method_agent_attempts").glob("*.json"))
    assert len(attempts) == 1
    attempt_id = attempts[0].stem
    supervisor = json.loads(
        (out_root / "artifacts" / "06_authoring" / "invocations"
         / f"run_supervisor_event.{attempt_id}.json").read_text(encoding="utf-8")
    )
    assert supervisor["parent_stop_signal"] == signal.SIGINT


def test_keyboard_interrupt_is_persisted_by_the_product_finalizer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture_repo = Path(__file__).resolve().parent / "fixtures" / "research_loop_project"

    def interrupt(*_args: object, **_kwargs: object) -> object:
        raise KeyboardInterrupt()

    monkeypatch.setattr(autonomous_method_agent, "_run_autonomous_method_agent_impl", interrupt)
    out_root = tmp_path / "keyboard-interrupt"
    with pytest.raises(KeyboardInterrupt):
        autonomous_method_agent.run_autonomous_method_agent(
            repo_path=fixture_repo,
            out_root=out_root,
            llm_config=LLMConfig(provider=LLMProvider.NONE),
            write_method_text=False,
            run_id="run-keyboard-interrupt",
            max_research_turns=2,
        )
    partial = json.loads(
        (out_root / "artifacts" / "research_product" / "run_summary.partial.json")
        .read_text(encoding="utf-8")
    )
    assert partial["terminal_reason"] == "keyboard_interrupt"


def test_unified_cli_forwards_full_method_agent_argument_set(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    forwarded: list[list[str]] = []

    def fake_supervisor(argv: list[str]) -> int:
        forwarded.append(list(argv))
        return 17

    monkeypatch.setattr(unified_cli, "supervised_method_agent_main", fake_supervisor)
    monkeypatch.delenv("CODE2PAPER_METHOD_AGENT_WORKER", raising=False)
    args = [
        "method-agent", "run",
        "--repo", str(Path(__file__).resolve().parent / "fixtures" / "research_loop_project"),
        "--out", str(tmp_path / "out"),
        "--max-research-turns", "60",
        "--max-wall-clock-seconds", "600",
        "--concept-cards", str(tmp_path / "cards.json"),
        "--compile-concept-cards",
        "--no-compile-argument-briefs",
        "--authoring-context-mode", "unified",
        "--research-stage-checkpoint", str(tmp_path / "checkpoint.json"),
    ]
    assert unified_cli.main(args) == 17
    assert forwarded == [args[1:]]


# ---------------------------------------------------------------------------
# Promotion-record dispositions and Candidate admission scope
# ---------------------------------------------------------------------------


def _superseded_record(
    obligation_id: str,
    *,
    observation_id: str = "observation:superseded",
    claim_ids: tuple[str, ...] = ("claim-core",),
) -> ObservationPromotionRecordV1:
    return ObservationPromotionRecordV1(
        observation_id=observation_id,
        obligation_id=obligation_id,
        tool_name="read_symbol",
        status="superseded",
        disposition_reason="replaced_by_compiled_evidence",
        superseding_claim_ids=claim_ids,
        superseding_compile_digest="sha256:compile",
    )


def _supported_item() -> ResearchAgendaItemV1:
    return ResearchAgendaItemV1(
        obligation_id="core-supported",
        priority="must_cover",
        status="supported",
        supported_claim_ids=["claim-core"],
        attempted_actions=["READ_CANDIDATE"],
    )


def _eligible_handoff(
    item: ResearchAgendaItemV1,
) -> tuple[CandidateHandoffV1, tuple[AtomicClaimV3, ...]]:
    claims, promotions = _handoff_inputs(item.obligation_id, "claim-core")
    handoff = build_candidate_handoff(
        run_id="run-candidate",
        repo_snapshot_id="repo:snapshot",
        project_tree_hash="sha256:tree",
        agenda_items=[item],
        promotion_records=promotions,
        compiled_claim_ids_by_obligation={item.obligation_id: ("claim-core",)},
        compiled_claims_by_obligation={item.obligation_id: claims},
    )
    assert handoff.eligible is True
    return handoff, claims


def test_explicit_terminal_dispositions_do_not_block_candidate_lane() -> None:
    from code2paper.agentic.research_promotion import (
        promotion_record_blocks_candidate,
        promotion_record_blocks_strict_research,
    )

    item = _supported_item()
    handoff, _claims = _eligible_handoff(item)

    superseded = _superseded_record(item.obligation_id)
    assert promotion_record_blocks_candidate(superseded, handoff, item) is False

    not_selected = ObservationPromotionRecordV1(
        observation_id="observation:not-selected",
        obligation_id=item.obligation_id,
        tool_name="search_symbols",
        status="not_selected",
        disposition_reason="observation_not_selected_for_compile",
    )
    assert promotion_record_blocks_candidate(not_selected, handoff, item) is False
    assert promotion_record_blocks_strict_research(not_selected) is False

    deferred = ObservationPromotionRecordV1(
        observation_id="observation:deferred",
        obligation_id="optional-later",
        tool_name="read_symbol",
        status="deferred",
        disposition_reason="non_core_observation_deferred_to_review",
    )
    assert promotion_record_blocks_candidate(deferred, handoff, item) is False

    incomplete = ObservationPromotionRecordV1(
        observation_id="observation:incomplete",
        obligation_id=item.obligation_id,
        tool_name="read_symbol",
        status="behavior_built",
        behavior_node_ids=("node:old",),
        rejection_code="evidence_packet_not_emitted",
    )
    assert promotion_record_blocks_candidate(incomplete, handoff, item) is True
    assert promotion_record_blocks_strict_research(incomplete) is True


def test_handoff_lineage_incomplete_observation_still_blocks() -> None:
    from code2paper.agentic.research_promotion import (
        promotion_record_blocks_candidate,
    )

    item = _supported_item()
    handoff, _claims = _eligible_handoff(item)
    bound_incomplete = ObservationPromotionRecordV1(
        observation_id="observation:bound-incomplete",
        obligation_id=item.obligation_id,
        tool_name="read_symbol",
        status="packet_promoted",
        behavior_node_ids=("node:core",),
        packet_ids=("packet:core",),
        rejection_code="code_fact_not_emitted",
        claim_ids=("claim-core",),
    )
    assert promotion_record_blocks_candidate(bound_incomplete, handoff, item) is True


def test_writer_preadmission_accepts_superseded_behavior_records(
    tmp_path: Path,
) -> None:
    from code2paper.agentic.research_models import ResearchAgendaV1
    from code2paper.agentic.research_promotion import ObservationPromotionLedgerV1

    item = _supported_item()
    agenda = ResearchAgendaV1(
        run_id="run-candidate",
        repo_snapshot_id="repo:snapshot",
        project_tree_hash="sha256:tree",
        items=[item],
    )
    agenda_path = tmp_path / "research_agenda_v1.json"
    agenda_path.write_text(agenda.model_dump_json(), encoding="utf-8")
    ledger = ObservationPromotionLedgerV1(
        repo_snapshot_id="repo:snapshot",
        project_tree_hash="sha256:tree",
        records=(
            _promotion("claim-core", item.obligation_id),
            _superseded_record(
                item.obligation_id, observation_id="observation:old:1"
            ),
            _superseded_record(
                item.obligation_id, observation_id="observation:old:2"
            ),
        ),
    )
    ledger_path = tmp_path / "observation_promotion_ledger_v1.json"
    ledger_path.write_text(ledger.model_dump_json(), encoding="utf-8")

    failures = publication_method_writer._writer_research_preadmission_failures(
        artifact_paths={
            "research_agenda_v1": str(agenda_path),
            "observation_promotion_ledger_v1": str(ledger_path),
        },
        required=(),
    )
    assert not any(
        failure.startswith("unified_observation_promotion_incomplete")
        for failure in failures
    )


def test_candidate_handoff_revalidation_survives_product_claim_canonicalization(
    tmp_path: Path,
) -> None:
    """Merged product claims remap ids; the frozen handoff must follow.

    Reproduces the live failure where the loop handoff referenced raw
    per-obligation claim ids while ``atomic_claims_v3`` carried canonical
    merged ids: the handoff looked eligible but the Writer's independent
    revalidation rebuilt an ineligible handoff and blocked Candidate.
    """

    from code2paper.agentic.evidence_compiler_v3 import (
        AtomicClaimSetV3,
        CodeFactSetV1,
        CodeFactV1,
        EvidencePacketSetV3,
        EvidencePacketV3,
        EvidenceSpanV3,
        RelationEvidenceV3,
    )
    from code2paper.agentic.publication_method_writer import (
        _candidate_handoff_revalidation_failures,
    )
    from code2paper.agentic.research_models import ResearchAgendaV1
    from code2paper.agentic.research_promotion import (
        ObservationPromotionLedgerV1,
        remap_promotion_ledger_claim_ids,
    )
    from code2paper.agentic.research_terminal import (
        build_candidate_handoff,
        build_candidate_retry_ledger,
    )

    run_id = "run-canonical"
    obligation_id = "OBL-CANON"
    fact_id = "fact-canon"
    span_id = "span:src/model.py:10:12"
    relation_id = "rel:canon"

    def _claim(claim_id: str, identity: str) -> AtomicClaimV3:
        return AtomicClaimV3(
            claim_id=claim_id,
            canonical_text="Model.forward branches on the observed flag",
            fact_ids=[fact_id],
            covers_obligation_ids=[obligation_id],
            direct_evidence_ids=[span_id],
            relation_evidence_ids=[relation_id],
            required_qualifiers=["the observed flag"],
            allowed_wording_boundary="Only the observed branch may be stated.",
            canonical_identity=identity,
        )

    raw_claim = _claim("claim-raw", "sha256:raw-identity")
    canonical_claim = _claim("claim-canonical", "sha256:canonical-identity")
    item = ResearchAgendaItemV1(
        obligation_id=obligation_id,
        priority="must_cover",
        status="supported",
        supported_claim_ids=["claim-raw"],
        attempted_actions=["READ_CANDIDATE"],
    )
    agenda = ResearchAgendaV1(
        run_id=run_id,
        repo_snapshot_id="repo:snapshot",
        project_tree_hash="sha256:tree",
        items=[item],
    )
    raw_ledger = ObservationPromotionLedgerV1(
        repo_snapshot_id="repo:snapshot",
        project_tree_hash="sha256:tree",
        records=(ObservationPromotionRecordV1(
            observation_id="observation:canon",
            obligation_id=obligation_id,
            tool_name="read_symbol",
            status="claim_promoted",
            behavior_node_ids=("node:canon",),
            packet_ids=("packet:canon",),
            fact_ids=(fact_id,),
            claim_ids=(raw_claim.claim_id,),
        ),),
    )
    retry_ledger = build_candidate_retry_ledger(
        run_id=run_id,
        repo_snapshot_id="repo:snapshot",
        project_tree_hash="sha256:tree",
    )

    ineligible = build_candidate_handoff(
        run_id=run_id,
        repo_snapshot_id="repo:snapshot",
        project_tree_hash="sha256:tree",
        agenda_items=(item,),
        promotion_records=raw_ledger.records,
        compiled_claims_by_obligation={obligation_id: (canonical_claim,)},
        post_partial_retry_counts={},
        agenda_digest=agenda.content_digest,
        promotion_ledger_digest=raw_ledger.content_digest,
        retry_ledger_digest=retry_ledger.content_digest,
    )
    assert ineligible.eligible is False
    assert (
        f"candidate_claim_set_binding_mismatch:{obligation_id}"
        in ineligible.eligibility_reasons
    )

    remapped_ledger = remap_promotion_ledger_claim_ids(
        raw_ledger,
        {raw_claim.claim_id: canonical_claim.claim_id},
    )
    assert remapped_ledger.records[0].claim_ids == (canonical_claim.claim_id,)
    assert remapped_ledger.content_digest != raw_ledger.content_digest
    assert remapped_ledger.content_digest == ObservationPromotionLedgerV1.model_validate_json(
        remapped_ledger.model_dump_json()
    ).content_digest

    rebuilt = build_candidate_handoff(
        run_id=run_id,
        repo_snapshot_id="repo:snapshot",
        project_tree_hash="sha256:tree",
        agenda_items=(item,),
        promotion_records=remapped_ledger.records,
        compiled_claims_by_obligation={obligation_id: (canonical_claim,)},
        post_partial_retry_counts={},
        agenda_digest=agenda.content_digest,
        promotion_ledger_digest=remapped_ledger.content_digest,
        retry_ledger_digest=retry_ledger.content_digest,
    )
    assert rebuilt.eligible is True

    span = EvidenceSpanV3(
        span_id=span_id,
        snapshot_id="repo:snapshot",
        project_tree_hash="sha256:tree",
        path="src/model.py",
        symbol="Model.forward",
        line_start=10,
        line_end=12,
        exact_excerpt="return self.flag",
        excerpt_digest="sha256:excerpt",
        file_digest="sha256:file",
        role="anchor",
    )
    packet_set = EvidencePacketSetV3(
        repo_snapshot_id="repo:snapshot",
        project_tree_hash="sha256:tree",
        packets=[EvidencePacketV3(
            packet_id="packet:canon",
            obligation_tags=[obligation_id],
            scope="sym:Model.forward",
            anchor_span_ids=[span_id],
            spans=[span],
            relations=[RelationEvidenceV3(
                relation_id=relation_id,
                relation_type="data_flow",
                source_symbol="Model.forward",
                target_symbol="Model.forward",
                statement="observed flag flows to the branch",
            )],
            source_digest="sha256:packet",
        )],
        content_digest="sha256:packets",
    )
    fact_set = CodeFactSetV1(
        repo_snapshot_id="repo:snapshot",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        facts=[CodeFactV1(
            fact_id=fact_id,
            subject="Model.forward",
            predicate="branches_on",
            object="observed flag",
            conditions=[],
            scope="sym:Model.forward",
            direct_span_ids=[span_id],
            relation_span_ids=[],
            relation_evidence_ids=[relation_id],
            exact_source_digest="sha256:fact",
            canonical_identity="sha256:fact-identity",
            validation_status="supported",
            validation_failures=[],
        )],
        content_digest="sha256:facts",
    )
    claim_set = AtomicClaimSetV3(
        repo_snapshot_id="repo:snapshot",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[canonical_claim],
        content_digest="sha256:claims",
    )

    paths = {
        "research_agenda_v1": tmp_path / "research_agenda_v1.json",
        "observation_promotion_ledger_v1": tmp_path / "observation_promotion_ledger_v1.json",
        "candidate_retry_ledger_v1": tmp_path / "candidate_retry_ledger_v1.json",
        "candidate_handoff_v1": tmp_path / "candidate_handoff_v1.json",
        "atomic_claims_v3": tmp_path / "atomic_claims_v3.json",
        "code_facts_v1": tmp_path / "code_facts_v1.json",
        "evidence_packets_v3": tmp_path / "evidence_packets_v3.json",
    }
    for payload, path in (
        (agenda, paths["research_agenda_v1"]),
        (remapped_ledger, paths["observation_promotion_ledger_v1"]),
        (retry_ledger, paths["candidate_retry_ledger_v1"]),
        (rebuilt, paths["candidate_handoff_v1"]),
        (claim_set, paths["atomic_claims_v3"]),
        (fact_set, paths["code_facts_v1"]),
        (packet_set, paths["evidence_packets_v3"]),
    ):
        path.write_text(payload.model_dump_json(), encoding="utf-8")

    failures = _candidate_handoff_revalidation_failures(
        artifact_paths={key: str(path) for key, path in paths.items()},
        handoff=rebuilt,
    )
    assert failures == ()


def test_legacy_explicit_gap_without_receipt_returns_to_research() -> None:
    """R9 migration: an old checkpoint gap is not negative evidence.

    A checkpoint written before the typed terminal contract carries
    ``status="explicit_gap"`` without a ledger-verified disposition.  The
    handoff must report that legacy record explicitly and keep the obligation
    out of the Writer as an exhausted gap.
    """

    from code2paper.agentic.research_models import GapRequirementV1

    legacy_item = ResearchAgendaItemV1(
        obligation_id="core-legacy-gap",
        priority="must_cover",
        status="explicit_gap",
        gap_requirements=[GapRequirementV1(
            requirement_id="gap-req:core-legacy-gap",
            description="Legacy bounded search recorded an exhaustion claim.",
            terminal="explicit_gap",
        )],
        missing_information=["bounded_search_exhausted"],
        attempted_actions=["SEARCH_SYMBOLS", "READ_CANDIDATE"],
    )
    handoff = build_candidate_handoff(
        run_id="run-legacy",
        repo_snapshot_id="repo:snapshot",
        project_tree_hash="sha256:tree",
        agenda_items=[legacy_item],
        promotion_records=(),
        agenda_digest="sha256:agenda",
        promotion_ledger_digest="sha256:promotions",
        retry_ledger_digest="sha256:retries",
    )
    assert handoff.eligible is False
    assert (
        "candidate_legacy_explicit_gap_unverified:core-legacy-gap"
        in handoff.eligibility_reasons
    )
    assert (
        "candidate_legacy_explicit_gap_unverified:core-legacy-gap"
        in handoff.warning_codes
    )
    assert "core-legacy-gap" not in handoff.supported_obligation_ids
    assert "core-legacy-gap" not in handoff.partial_obligation_ids
    # The same item still reads as a non-terminal obligation.
    proof = evaluate_obligation_terminal_proof(legacy_item)
    assert proof.terminal is False


def test_legacy_gap_round_trip_blocks_the_writer_preadmission(tmp_path: Path) -> None:
    """R9 migration round trip: checkpoint -> coverage -> handoff -> Writer.

    A pre-R9 checkpoint records ``explicit_gap`` without a ledger-verified
    disposition.  The handoff reports the legacy record and the Writer's
    Research pre-admission refuses to treat the obligation as terminated, so
    the old gap can never enter the paper as an exhausted conclusion.
    """

    from code2paper.agentic.research_models import (
        GapRequirementV1,
        ResearchAgendaV1,
    )
    from code2paper.agentic.publication_method_writer import (
        _writer_research_preadmission_failures,
    )

    legacy_item = ResearchAgendaItemV1(
        obligation_id="O-LEGACY-GAP",
        priority="must_cover",
        status="explicit_gap",
        gap_requirements=[GapRequirementV1(
            requirement_id="gap-req:O-LEGACY-GAP",
            description="Legacy bounded search recorded an exhaustion claim.",
            terminal="explicit_gap",
        )],
        missing_information=["bounded_search_exhausted"],
        attempted_actions=["SEARCH_SYMBOLS", "READ_CANDIDATE"],
    )
    agenda = ResearchAgendaV1(
        run_id="run-legacy-round-trip",
        repo_snapshot_id="repo:snapshot",
        project_tree_hash="sha256:tree",
        items=[legacy_item],
    )
    agenda_path = tmp_path / "research_agenda_v1.json"
    agenda_path.write_text(agenda.model_dump_json(), encoding="utf-8")

    # Coverage/handoff step: the legacy gap is reported as unverified.
    handoff = build_candidate_handoff(
        run_id="run-legacy-round-trip",
        repo_snapshot_id="repo:snapshot",
        project_tree_hash="sha256:tree",
        agenda_items=[legacy_item],
        promotion_records=(),
        agenda_digest="sha256:agenda",
        promotion_ledger_digest="sha256:promotions",
        retry_ledger_digest="sha256:retries",
    )
    assert handoff.eligible is False
    assert (
        "candidate_legacy_explicit_gap_unverified:O-LEGACY-GAP"
        in handoff.eligibility_reasons
    )
    handoff_path = tmp_path / "candidate_handoff_v1.json"
    handoff_path.write_text(handoff.model_dump_json(), encoding="utf-8")

    # Writer pre-admission step: the obligation is still non-terminal.
    failures = _writer_research_preadmission_failures(
        artifact_paths={
            "research_agenda_v1": str(agenda_path),
            "candidate_handoff_v1": str(handoff_path),
        },
        required=("research_agenda_v1",),
    )
    assert (
        "unified_core_intent_terminal_proof_missing:O-LEGACY-GAP" in failures
    ), failures
