"""Review P0-Q4 tests: Writer callbacks continue the ORIGINAL Research
LangGraph through the persisted research stage checkpoint.

The callback request becomes a new scoped obligation on the restored child
research state; the existing research subgraph runs with an additive tool
budget; fulfillment is decided by an owning validator report (never
self-authorized); the full chain (observations -> behavior graph -> evidence
packet -> fact -> claim -> Concept judgment -> placement -> WriterView) is
persisted; and only the affected section resumes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from code2paper.agentic.autonomous_method_agent import (
    UserClaimsInputV1,
    build_product_research_runtime,
    merge_product_evidence,
    persist_research_stage_checkpoint,
    run_product_research_phase,
)
from code2paper.agentic.method_argument_models import (
    WritingResearchCallbackBundleV1,
    WritingResearchRequestV1,
)
from code2paper.agentic.writing_callback_fulfillment import (
    WritingCallbackFulfillmentBudgetV1,
    build_research_continuation_seed,
    fulfill_and_resume_writing_callbacks,
)
from code2paper.schemas import LLMConfig, LLMProvider
from tests.tempdir_support import workspace_tempdir


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_REPO = ROOT / "tests" / "fixtures" / "research_loop_project"
FIXTURE_INTENT = ROOT / "tests" / "fixtures" / "research_loop_project_author_markers.yaml"


def _llm_none() -> LLMConfig:
    return LLMConfig(provider=LLMProvider.NONE, model="none")


def _research_checkpoint(tmp: Path) -> tuple[object, str]:
    """Run a bounded deterministic research phase and freeze the stage
    checkpoint (the persisted child research state)."""

    runtime = build_product_research_runtime(
        repo_path=FIXTURE_REPO,
        author_intent_path=FIXTURE_INTENT,
        claims=None,
        run_id="continuation-test",
        llm_config=_llm_none(),
        artifact_root=tmp / "artifacts" / "research_tool_data",
    )
    result = run_product_research_phase(runtime, max_turns=20)
    assert result.turns_executed > 0
    packets, facts, claims = merge_product_evidence(result, runtime)
    checkpoint = persist_research_stage_checkpoint(
        out_root=tmp,
        runtime=runtime,
        claims_input=UserClaimsInputV1(claims=[]),
        loop_result=result,
        packet_set=packets,
        fact_set=facts,
        claim_set=claims,
    )
    return runtime, checkpoint


def _bundle(tmp: Path, request: WritingResearchRequestV1) -> tuple[Path, dict[str, str]]:
    bundle_dir = tmp / "artifacts" / "06_authoring"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = bundle_dir / "writing_research_callback_artifacts_v1.json"
    bundle = WritingResearchCallbackBundleV1(requests=(request,))
    bundle_path.write_text(bundle.model_dump_json(indent=2) + "\n", encoding="utf-8")
    writer_paths = {
        "writing_research_callback_artifacts_v1": str(bundle_path),
        "publication_section_checkpoint_v1": str(
            bundle_dir / "publication_section_checkpoint_v1.json"
        ),
    }
    return bundle_path, writer_paths


def _request(*, request_id: str = "request:cont:1", symbol: str = "run_training") -> WritingResearchRequestV1:
    return WritingResearchRequestV1(
        request_id=request_id,
        section_id="MA-S1",
        argument_unit_id="MA-S1:unit",
        missing_rhetorical_move="implementation_realization",
        exact_question=f"Find the repository evidence for {symbol}.",
        required_authority_lane="executable_hard",
        candidate_symbols_or_terms=(symbol,),
        current_known_facts=(),
        priority="high",
    )


def _run_loop(
    tmp: Path,
    runtime: object,
    checkpoint: str,
    bundle_path: Path,
    writer_paths: dict[str, str],
    budget: WritingCallbackFulfillmentBudgetV1 | None = None,
) -> tuple[object, list[dict]]:
    resume_calls: list[dict] = []

    def _fake_writer(out_root, artifact_paths, llm_config, llm_caller=None,
                     resume_section_ids=(), research_callback_artifacts=None,
                     **kwargs):
        resume_calls.append({
            "resume_section_ids": tuple(resume_section_ids),
            "callback_artifacts": sorted(research_callback_artifacts or {}),
        })
        class _Result:
            status = "success" if resume_section_ids else "incomplete"
            blocked_reason = ""
        return _Result(), writer_paths

    from code2paper.agentic import writing_callback_fulfillment as module

    with patch.object(module, "run_publication_method_writer", _fake_writer):
        _paths, status, reason, result = fulfill_and_resume_writing_callbacks(
            runtime=runtime,
            out_root=tmp,
            artifact_paths={},
            writer_paths=writer_paths,
            llm_config=_llm_none(),
            budget=budget or WritingCallbackFulfillmentBudgetV1(
                max_callback_rounds=2, max_tool_turns_per_request=15,
            ),
            research_stage_checkpoint=checkpoint,
        )
    return result, resume_calls


def test_continuation_fulfills_request_through_original_research_graph() -> None:
    """A repository request is fulfilled by restoring the SAME research
    thread/checkpoint and invoking the original research subgraph with an
    additive budget; the owning validator report authorizes fulfillment."""

    with workspace_tempdir() as tmpdir:
        tmp = Path(tmpdir)
        runtime, checkpoint = _research_checkpoint(tmp)
        bundle_path, writer_paths = _bundle(tmp, _request())
        result, resume_calls = _run_loop(tmp, runtime, checkpoint, bundle_path, writer_paths)

        assert result.local_requests_seen == 1
        assert result.local_requests_fulfilled == 1
        assert result.resumed_section_ids == ("MA-S1",)
        assert result.stopped_reason == "writer_success"
        assert resume_calls and resume_calls[0]["resume_section_ids"] == ("MA-S1",)
        assert "request:cont:1" in resume_calls[0]["callback_artifacts"]

        updated = WritingResearchCallbackBundleV1.model_validate_json(
            bundle_path.read_text(encoding="utf-8")
        )
        assert updated.requests[0].status == "fulfilled"
        artifact_id = updated.requests[0].fulfilled_artifact_ids[0]
        artifact_dir = tmp / "artifacts" / "research_tool_data" / "writing_callbacks" / "request:cont:1"
        artifact_file = artifact_dir / f"{artifact_id}.json"
        assert artifact_file.is_file()
        payload = json.loads(artifact_file.read_text(encoding="utf-8"))
        # Owning validator report: validated is a pure function of the checks,
        # never self-authorized.
        report = payload["validator_report"]
        assert report["validated"] is True
        assert report["reasons"] == []
        assert report["validator"] == "research_graph_compile_gates_and_closure_checks"
        # The full chain record is persisted and digest-pinned.
        chain_path = (tmp / "artifacts" / "06_authoring" / payload["chain_record_ref"]).resolve()
        assert chain_path.is_file()
        chain = json.loads(chain_path.read_text(encoding="utf-8"))
        assert chain["research_thread"]["run_id"] == "continuation-test"
        assert chain["research_thread"]["checkpoint_digest"].startswith("sha256:")
        assert chain["behavior_graph"]["content_digest"].startswith("sha256:")
        assert chain["evidence_packets"], "new evidence packet must be compiled"
        assert chain["facts"], "new facts must be compiled"
        assert chain["claims"], "new claims must be compiled"
        assert chain["observations"], "new observations must be recorded"
        assert chain["decision_trace"], "the research graph decision trace must continue"
        assert chain["termination"]["termination_reason"] in {
            "all_obligations_terminal", "max_turns_reached", "ready_to_author",
        }
        # The artifact itself is digest-pinned (owning-validator binding).
        digest = "sha256:" + hashlib.sha256(artifact_file.read_bytes()).hexdigest()
        assert digest == updated.artifacts["request:cont:1"][0].artifact_digest


def test_continuation_requires_new_evidence_beyond_used_refs() -> None:
    """Stage-5 fail-closed rule preserved on the continuation path: a request
    whose pre-bound refs already cover the target evidence stays pending; the
    owning validator report refuses fulfillment."""

    with workspace_tempdir() as tmpdir:
        tmp = Path(tmpdir)
        runtime, checkpoint = _research_checkpoint(tmp)
        reused = _request(request_id="request:reuse").model_copy(update={
            "evidence_refs_used": (
                "span:compute.py:3:3", "span:compute.py:4:4",
                "span:compute.py:6:6", "span:compute.py:8:8",
            ),
            "missing_parts": ("scaling behavior",),
            "concept_key": "CK-SCALE",
        })
        bundle_path, writer_paths = _bundle(tmp, reused)
        result, resume_calls = _run_loop(tmp, runtime, checkpoint, bundle_path, writer_paths)

        assert result.local_requests_fulfilled == 0
        assert result.resumed_section_ids == ()
        assert not resume_calls
        updated = WritingResearchCallbackBundleV1.model_validate_json(
            bundle_path.read_text(encoding="utf-8")
        )
        assert updated.requests[0].status == "open"


def test_continuation_persists_concept_judgment_and_placement() -> None:
    """The chain projects the new evidence onto Concept cards (exact span
    binding) and section placement; only the affected section resumes."""

    from code2paper.agentic.method_concept_card_models import (
        ConceptCardBindingV1,
        MethodConceptCardSetV1,
        MethodConceptCardV1,
    )

    with workspace_tempdir() as tmpdir:
        tmp = Path(tmpdir)
        runtime, checkpoint = _research_checkpoint(tmp)
        # Concept card bound to the exact span the continuation will observe.
        card = MethodConceptCardV1(
            concept_key="CK-RUN", authority_lane="repository",
            method_subject="training entry point",
            operation="runs training on the input values",
            may_enter_verified=True,
        )
        card_set = MethodConceptCardSetV1(
            repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
            project_tree_hash=runtime.repo_snapshot.project_tree_hash,
            cards=[card],
            bindings=[ConceptCardBindingV1(
                concept_key="CK-RUN",
                source_obligation_ids=(),
                source_span_ids=("span:compute.py:3:3",),
            )],
        )
        card_path = tmp / "artifacts" / "method_concept_cards_v1.json"
        card_path.parent.mkdir(parents=True, exist_ok=True)
        card_path.write_text(card_set.model_dump_json(indent=2) + "\n", encoding="utf-8")

        bundle_path, writer_paths = _bundle(tmp, _request())
        resume_calls: list[dict] = []

        def _fake_writer(out_root, artifact_paths, llm_config, llm_caller=None,
                         resume_section_ids=(), research_callback_artifacts=None,
                         **kwargs):
            resume_calls.append(tuple(resume_section_ids))
            class _Result:
                status = "success"
                blocked_reason = ""
            return _Result(), writer_paths

        from code2paper.agentic import writing_callback_fulfillment as module

        with patch.object(module, "run_publication_method_writer", _fake_writer), \
             patch.object(module, "_load_concept_cards", return_value=card_set):
            _paths, _status, _reason, result = fulfill_and_resume_writing_callbacks(
                runtime=runtime,
                out_root=tmp,
                artifact_paths={},
                writer_paths=writer_paths,
                llm_config=_llm_none(),
                budget=WritingCallbackFulfillmentBudgetV1(
                    max_callback_rounds=2, max_tool_turns_per_request=15,
                ),
                research_stage_checkpoint=checkpoint,
            )

        assert result.local_requests_fulfilled == 1
        assert result.resumed_section_ids == ("MA-S1",)
        assert resume_calls == [("MA-S1",)]
        updated = WritingResearchCallbackBundleV1.model_validate_json(
            bundle_path.read_text(encoding="utf-8")
        )
        artifact_id = updated.requests[0].fulfilled_artifact_ids[0]
        artifact_file = (
            tmp / "artifacts" / "research_tool_data" / "writing_callbacks"
            / "request:cont:1" / f"{artifact_id}.json"
        )
        payload = json.loads(artifact_file.read_text(encoding="utf-8"))
        assert "CK-RUN" in payload["concept_judgment"]
        placement = payload["placement"]
        assert placement["affected_sections"] == ["MA-S1"]
        assert "MA-S1:unit" in placement["sections"]["MA-S1"]
        # The chain record carries the same judgment and placement.
        chain = json.loads(
            (tmp / "artifacts" / "06_authoring" / payload["chain_record_ref"]).read_text(
                encoding="utf-8"
            )
        )
        assert "CK-RUN" in chain["concept_judgment"]
        assert chain["placement"]["affected_sections"] == ["MA-S1"]


def test_continuation_checkpoint_mismatch_falls_back_to_legacy_provider() -> None:
    """A checkpoint that does not authenticate (foreign run id) cannot
    continue the research thread; the loop degrades to the explicitly legacy
    provider path and records the typed error instead of crashing."""

    with workspace_tempdir() as tmpdir:
        tmp = Path(tmpdir)
        runtime, checkpoint = _research_checkpoint(tmp)
        payload = json.loads(Path(checkpoint).read_text(encoding="utf-8"))
        payload["run_id"] = "foreign-run"
        Path(checkpoint).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        bundle_path, writer_paths = _bundle(tmp, _request())
        result, resume_calls = _run_loop(tmp, runtime, checkpoint, bundle_path, writer_paths)
        # No crash; the legacy path cannot fulfill without frozen facts, so
        # the request stays pending and the error is traced.
        assert result.local_requests_fulfilled == 0
        trace_path = Path(result.trace_path)
        assert trace_path.is_file()
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        assert "research_graph_continuation_error" in trace
        assert "run_id" in trace["research_graph_continuation_error"]


def test_continuation_reuses_the_same_thread_agenda_and_decision_history() -> None:
    """The continuation appends ONE scoped obligation to the restored agenda
    and never mutates the persisted child research state."""

    with workspace_tempdir() as tmpdir:
        tmp = Path(tmpdir)
        runtime, checkpoint = _research_checkpoint(tmp)
        checkpoint_payload = json.loads(Path(checkpoint).read_text(encoding="utf-8"))
        original_obligation_ids = [
            item["obligation_id"] for item in checkpoint_payload["agenda"]["items"]
        ]
        original_decision_count = len(checkpoint_payload["decision_trace"] or ())

        bundle_path, writer_paths = _bundle(tmp, _request())
        result, _resume_calls = _run_loop(tmp, runtime, checkpoint, bundle_path, writer_paths)
        assert result.local_requests_fulfilled == 1

        callback_obligation_ids = [
            item.obligation_id
            for item in runtime.agenda.items
            if item.obligation_id.startswith("callback:")
        ]
        assert callback_obligation_ids == ["callback:request:cont:1"]
        # The persisted child research state is untouched.
        after = json.loads(Path(checkpoint).read_text(encoding="utf-8"))
        assert [item["obligation_id"] for item in after["agenda"]["items"]] == original_obligation_ids
        assert len(after["decision_trace"] or ()) == original_decision_count


def test_reconstructed_seed_restores_frozen_authority_without_fake_history() -> None:
    """A missing checkpoint uses a typed seed, never synthetic checkpoint data."""

    from code2paper.agentic.autonomous_method_agent import build_product_research_runtime
    from code2paper.agentic.intent_compiler_v2 import IntentObligationGraphV2
    from code2paper.agentic.research_models import ResearchAgendaV1
    from code2paper.agentic.writing_callback_fulfillment import (
        _ResearchGraphContinuationProvider,
    )

    with workspace_tempdir() as tmpdir:
        tmp = Path(tmpdir)
        original_runtime, checkpoint = _research_checkpoint(tmp)
        checkpoint_payload = json.loads(Path(checkpoint).read_text(encoding="utf-8"))
        artifact_dir = tmp / "artifacts"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        frozen_payloads = {
            "intent_obligation_graph_v2": checkpoint_payload["intent_graph"],
            "research_agenda_v1": checkpoint_payload["agenda"],
            "evidence_packets_v3": checkpoint_payload["evidence_packets"],
            "code_facts_v1": checkpoint_payload["code_facts"],
            "atomic_claims_v3": checkpoint_payload["atomic_claims"],
            "user_claims_input_v1": checkpoint_payload["claims_input"],
        }
        artifact_paths: dict[str, str] = {}
        for name, payload in frozen_payloads.items():
            path = artifact_dir / f"{name}.json"
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            artifact_paths[name] = str(path)

        runtime = build_product_research_runtime(
            repo_path=FIXTURE_REPO,
            author_intent_path=None,
            claims=None,
            run_id=original_runtime.run_id,
            llm_config=_llm_none(),
            artifact_root=artifact_dir / "research_tool_data",
            intent_graph_override=IntentObligationGraphV2.model_validate(
                checkpoint_payload["intent_graph"]
            ),
            agenda_override=ResearchAgendaV1.model_validate(
                checkpoint_payload["agenda"]
            ),
        )
        seed, seed_path = build_research_continuation_seed(
            runtime=runtime,
            artifact_paths=artifact_paths,
            out_root=tmp,
        )
        assert seed.origin == "reconstructed_from_frozen_authority"
        assert seed.past_decision_trace_available is False
        assert "checkpoint" not in Path(seed_path).name
        seed_payload = json.loads(Path(seed_path).read_text(encoding="utf-8"))
        assert "decision_trace" not in seed_payload
        assert "research_stage_checkpoint" not in seed_payload

        provider = _ResearchGraphContinuationProvider(
            runtime=runtime,
            research_stage_checkpoint=None,
            research_continuation_seed=seed,
            facts=None,
            plan=None,
            concept_cards=None,
            callback_root=artifact_dir / "06_authoring",
            budget=WritingCallbackFulfillmentBudgetV1(max_tool_turns_per_request=5),
            artifact_paths=artifact_paths,
            llm_config=_llm_none(),
        )
        restored = provider._restore_loop()
        assert "frozen-authority" in restored.compiled_evidence
        assert not restored.decision_trace


def test_unanchored_equation_callback_routes_to_formalizer_not_repository() -> None:
    from code2paper.agentic.writer_research_router import route_writing_research_request

    request = WritingResearchRequestV1(
        request_id="request:eq",
        section_id="MA-S1",
        argument_unit_id="MA-S1:unit",
        missing_rhetorical_move="equation_or_derivation",
        exact_question="Which formula package closes this unanchored move?",
        required_authority_lane="formal_derivation",
        candidate_symbols_or_terms=(),
        current_known_facts=(),
        priority="high",
    )
    route = route_writing_research_request(request)
    assert route.owner == "formalization_agent"
    assert route.owner != "repository_tools"


def test_baseline_binding_missing_when_only_frag_refs() -> None:
    """Slice 4A: frag-* refs without digest-bound spans must not yield an
    empty baseline and proceed; fulfillment stops with baseline_binding_missing."""

    from code2paper.agentic.writing_callback_fulfillment import (
        resolve_request_baseline_spans,
    )

    request = WritingResearchRequestV1(
        request_id="request:frag",
        section_id="MA-S1",
        argument_unit_id="MA-S1:unit",
        missing_rhetorical_move="implementation_realization",
        exact_question="Which evidence resolves the caveated concept?",
        required_authority_lane="executable_hard",
        candidate_symbols_or_terms=("run_training",),
        concept_key="CK-SCALE",
        missing_parts=("scaling behavior",),
        evidence_refs_used=("frag-1", "frag-2"),
        priority="high",
    )
    spans, reasons = resolve_request_baseline_spans(
        request,
        require_resolvable=True,
    )
    assert spans == ()
    assert "baseline_binding_missing" in reasons
    assert any(item.startswith("unresolved_frag_refs:") for item in reasons)

    with workspace_tempdir() as tmpdir:
        tmp = Path(tmpdir)
        runtime, checkpoint = _research_checkpoint(tmp)
        bundle_path, writer_paths = _bundle(tmp, request)
        result, resume_calls = _run_loop(tmp, runtime, checkpoint, bundle_path, writer_paths)

        assert result.local_requests_fulfilled == 0
        assert result.resumed_section_ids == ()
        assert not resume_calls
        updated = WritingResearchCallbackBundleV1.model_validate_json(
            bundle_path.read_text(encoding="utf-8")
        )
        assert updated.requests[0].status == "open"


def test_off_target_concept_judgment_keeps_request_open() -> None:
    """Slice 4A: concept judgment must hit the request target concept, not a
    neighboring card on the same obligation."""

    from code2paper.agentic.method_concept_card_models import (
        ConceptCardBindingV1,
        MethodConceptCardSetV1,
        MethodConceptCardV1,
    )
    from code2paper.agentic.writing_callback_fulfillment import (
        _ResearchGraphContinuationProvider,
        _validate_concept_judgment_target,
    )

    failures = _validate_concept_judgment_target(
        WritingResearchRequestV1(
            request_id="request:off-target",
            section_id="MA-S1",
            argument_unit_id="MA-S1:unit",
            missing_rhetorical_move="implementation_realization",
            exact_question="Which evidence binds the attention mask?",
            required_authority_lane="executable_hard",
            candidate_symbols_or_terms=("run_training",),
            concept_key="CK-ATTN",
            missing_parts=("attention mask",),
            evidence_refs_used=("span:compute.py:3:3",),
            baseline_span_ids=("span:compute.py:3:3",),
            priority="high",
        ),
        {"CK-POS": ["span:compute.py:6:6"]},
    )
    assert failures == ["off_target_concept_judgment:CK-POS"]

    with workspace_tempdir() as tmpdir:
        tmp = Path(tmpdir)
        runtime, checkpoint = _research_checkpoint(tmp)
        attn_card = MethodConceptCardV1(
            concept_key="CK-ATTN",
            authority_lane="repository",
            method_subject="attention mask",
            operation="masks same-document passages",
            may_enter_verified=False,
            missing_parts=("attention mask",),
        )
        pos_card = MethodConceptCardV1(
            concept_key="CK-POS",
            authority_lane="repository",
            method_subject="positional encoding",
            operation="adds passage position vectors",
            may_enter_verified=True,
        )
        card_set = MethodConceptCardSetV1(
            repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
            project_tree_hash=runtime.repo_snapshot.project_tree_hash,
            cards=[attn_card, pos_card],
            bindings=[
                ConceptCardBindingV1(
                    concept_key="CK-ATTN",
                    source_obligation_ids=(),
                    source_span_ids=("span:compute.py:3:3",),
                ),
                ConceptCardBindingV1(
                    concept_key="CK-POS",
                    source_obligation_ids=(),
                    source_span_ids=("span:compute.py:6:6",),
                ),
            ],
        )
        request = WritingResearchRequestV1(
            request_id="request:off-target",
            section_id="MA-S1",
            argument_unit_id="MA-S1:unit",
            missing_rhetorical_move="implementation_realization",
            exact_question="Which evidence binds the attention mask?",
            required_authority_lane="executable_hard",
            candidate_symbols_or_terms=("run_training",),
            concept_key="CK-ATTN",
            missing_parts=("attention mask",),
            evidence_refs_used=("span:compute.py:3:3",),
            baseline_span_ids=("span:compute.py:3:3",),
            priority="high",
        )
        provider = _ResearchGraphContinuationProvider(
            runtime=runtime,
            research_stage_checkpoint=checkpoint,
            facts=None,
            plan=None,
            concept_cards=card_set,
            callback_root=tmp / "callbacks",
            budget=WritingCallbackFulfillmentBudgetV1(
                max_tool_turns_per_request=5,
            ),
            artifact_paths={},
        )
        report = provider._owning_validator_report(
            request=request,
            obligation_id="callback:request:off-target",
            compiled=type(
                "Compiled",
                (),
                {
                    "packet_set": type("Packets", (), {"packets": [type("P", (), {"packet_id": "pkt:1"})()]})(),
                    "fact_set": type(
                        "Facts",
                        (),
                        {
                            "facts": [
                                type(
                                    "Fact",
                                    (),
                                    {
                                        "fact_id": "fact:new",
                                        "validation_status": "supported",
                                        "direct_span_ids": ("span:compute.py:6:6",),
                                        "relation_span_ids": (),
                                    },
                                )(),
                            ],
                        },
                    )(),
                    "claim_set": type(
                        "Claims",
                        (),
                        {
                            "claims": [
                                type(
                                    "Claim",
                                    (),
                                    {
                                        "claim_id": "claim:new",
                                        "status": "supported",
                                        "covers_obligation_ids": (
                                            "callback:request:off-target",
                                        ),
                                    },
                                )(),
                            ],
                        },
                    )(),
                },
            )(),
            baseline_spans={"span:compute.py:3:3"},
        )
        assert report["validated"] is False
        assert any(
            str(item).startswith("off_target_concept_judgment:")
            for item in report["reasons"]
        )


def test_partial_slot_progress_marks_request_partial_without_fulfill() -> None:
    """Slice 4B: partial mandatory-slot progress keeps remaining slots on the request."""

    from code2paper.agentic.publication_method_writer import fulfill_writing_research_callbacks

    request = WritingResearchRequestV1(
        request_id="request:partial-slots",
        section_id="MA-S1",
        argument_unit_id="MA-S1:unit",
        missing_rhetorical_move="algorithm_or_data_flow",
        exact_question="How does data flow?",
        required_authority_lane="executable_hard",
        candidate_symbols_or_terms=("forward",),
        mandatory_missing_slots=("input", "transformation", "output"),
        priority="high",
    )
    with workspace_tempdir() as tmpdir:
        tmp = Path(tmpdir)
        bundle_path, _ = _bundle(tmp, request)
        updated = fulfill_writing_research_callbacks(
            bundle_path,
            {},
            slot_progress={
                "request:partial-slots": (("input", "transformation"), ("output",)),
            },
        )
        partial = updated.requests[0]
        assert partial.status == "partial"
        assert "input" in partial.satisfied_slots
        assert partial.remaining_slots == ("output",)


def test_partial_callback_keeps_validated_artifacts_and_remaining_slots() -> None:
    """Live DyG 234431: search returned partial slots, then bundle validation
    rejected fulfilled_artifact_ids on status=partial and Writer never resumed.
    """

    from code2paper.agentic.method_argument_models import WritingResearchCallbackArtifactV1
    from code2paper.agentic.publication_method_writer import fulfill_writing_research_callbacks

    request = WritingResearchRequestV1(
        request_id="request:partial-artifact",
        section_id="MA-S1",
        argument_unit_id="MA-S1:unit-1",
        missing_rhetorical_move="mechanism_overview",
        exact_question="Which repository spans, symbols, or functions implement: encoding?",
        required_authority_lane="executable_hard",
        candidate_symbols_or_terms=("encoding",),
        mandatory_missing_slots=("input", "transformation", "relation"),
        priority="high",
    )
    artifact = WritingResearchCallbackArtifactV1(
        artifact_id="writing-callback:request:partial-artifact:abc123",
        request_id=request.request_id,
        section_id=request.section_id,
        argument_unit_id=request.argument_unit_id,
        authority_lane="executable_hard",
        artifact_ref="span:encoder.py:10:12",
        artifact_digest="sha256:partial-progress",
        validated=True,
    )
    with workspace_tempdir() as tmpdir:
        tmp = Path(tmpdir)
        bundle_path, _ = _bundle(tmp, request)
        updated = fulfill_writing_research_callbacks(
            bundle_path,
            {request.request_id: (artifact,)},
            slot_progress={
                request.request_id: (("relation", "transformation"), ("input",)),
            },
        )
        partial = updated.requests[0]
        assert partial.status == "partial"
        assert partial.fulfilled_artifact_ids == (artifact.artifact_id,)
        assert partial.remaining_slots == ("input",)
        assert updated.artifacts[request.request_id][0].artifact_id == artifact.artifact_id
        assert "MA-S1" in updated.resume_section_ids



def test_two_of_three_slots_is_partial_not_full_fulfill() -> None:
    """Slice 4B: 2/3 mandatory slots keep remaining output and stay partial."""

    from code2paper.agentic.method_concept_card_models import (
        ConceptCardBindingV1,
        MethodConceptCardSetV1,
        MethodConceptCardV1,
    )
    from code2paper.agentic.writing_callback_fulfillment import (
        WritingCallbackFulfillmentBudgetV1,
        _ResearchGraphContinuationProvider,
    )

    with workspace_tempdir() as tmpdir:
        tmp = Path(tmpdir)
        runtime, checkpoint = _research_checkpoint(tmp)
        card_set = MethodConceptCardSetV1(
            repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
            project_tree_hash=runtime.repo_snapshot.project_tree_hash,
            cards=[
                MethodConceptCardV1(
                    concept_key="CK-CORE",
                    authority_lane="repository",
                    method_subject="core transform",
                    operation="maps inputs to outputs",
                    may_enter_verified=True,
                ),
            ],
            bindings=[
                ConceptCardBindingV1(
                    concept_key="CK-CORE",
                    source_obligation_ids=(),
                    source_span_ids=("span:compute.py:10:12",),
                ),
            ],
        )
        request = WritingResearchRequestV1(
            request_id="request:partial-3",
            section_id="MA-S1",
            argument_unit_id="MA-S1:unit",
            missing_rhetorical_move="algorithm_or_data_flow",
            exact_question="How does data flow from input to output?",
            required_authority_lane="executable_hard",
            candidate_symbols_or_terms=("forward",),
            concept_key="CK-CORE",
            mandatory_missing_slots=("input", "transformation", "output"),
            baseline_span_ids=("span:compute.py:1:2",),
            priority="high",
        )
        provider = _ResearchGraphContinuationProvider(
            runtime=runtime,
            research_stage_checkpoint=checkpoint,
            facts=None,
            plan=None,
            concept_cards=card_set,
            callback_root=tmp / "callbacks",
            budget=WritingCallbackFulfillmentBudgetV1(max_tool_turns_per_request=5),
            artifact_paths={},
        )
        report = provider._owning_validator_report(
            request=request,
            obligation_id="callback:request:partial-3",
            compiled=type(
                "Compiled",
                (),
                {
                    "packet_set": type("Packets", (), {"packets": [type("P", (), {"packet_id": "pkt:1"})()]})(),
                    "fact_set": type(
                        "Facts",
                        (),
                        {
                            "facts": [
                                type(
                                    "Fact",
                                    (),
                                    {
                                        "fact_id": "fact:new",
                                        "validation_status": "supported",
                                        "direct_span_ids": ("span:compute.py:10:12",),
                                        "relation_span_ids": (),
                                        "subject": "encoder",
                                        "predicate": "transforms",
                                        "object": "tokens",
                                        "canonical_identity": "",
                                    },
                                )(),
                            ],
                        },
                    )(),
                    "claim_set": type(
                        "Claims",
                        (),
                        {
                            "claims": [
                                type(
                                    "Claim",
                                    (),
                                    {
                                        "claim_id": "claim:new",
                                        "status": "supported",
                                        "covers_obligation_ids": (
                                            "callback:request:partial-3",
                                        ),
                                    },
                                )(),
                            ],
                        },
                    )(),
                },
            )(),
            baseline_spans={"span:compute.py:1:2"},
        )
        assert report["validated"] is True
        assert report["partial"] is True
        assert "output" in report["remaining_slots"]
        assert set(report["satisfied_slots"]) >= {"input", "transformation"}


def test_incomplete_research_with_remaining_slots_is_not_fulfilled() -> None:
    from code2paper.agentic.writing_callback_fulfillment import (
        WritingCallbackFulfillmentBudgetV1,
        _ResearchGraphContinuationProvider,
    )

    with workspace_tempdir() as tmpdir:
        tmp = Path(tmpdir)
        runtime, checkpoint = _research_checkpoint(tmp)
        request = WritingResearchRequestV1(
            request_id="request:incomplete",
            section_id="MA-S1",
            argument_unit_id="MA-S1:unit",
            missing_rhetorical_move="implementation_realization",
            exact_question="How is the core transform implemented?",
            required_authority_lane="executable_hard",
            candidate_symbols_or_terms=("forward",),
            mandatory_missing_slots=("input", "transformation", "output"),
            baseline_span_ids=("span:compute.py:1:2",),
            priority="high",
        )
        provider = _ResearchGraphContinuationProvider(
            runtime=runtime,
            research_stage_checkpoint=checkpoint,
            facts=None,
            plan=None,
            concept_cards=None,
            callback_root=tmp / "callbacks",
            budget=WritingCallbackFulfillmentBudgetV1(max_tool_turns_per_request=5),
            artifact_paths={},
        )
        report = provider._owning_validator_report(
            request=request,
            obligation_id="callback:request:incomplete",
            compiled=type(
                "Compiled",
                (),
                {
                    "packet_set": type("Packets", (), {"packets": []})(),
                    "fact_set": type("Facts", (), {"facts": []})(),
                    "claim_set": type("Claims", (), {"claims": []})(),
                },
            )(),
            baseline_spans={"span:compute.py:1:2"},
        )
        assert report["validated"] is False
        assert report.get("partial") is False
        assert "no_facts_compiled" in report["reasons"]


def test_same_canonical_fingerprint_is_not_information_gain() -> None:
    from code2paper.agentic.callback_semantic_contract import canonical_fact_fingerprint
    from code2paper.agentic.writing_callback_fulfillment import (
        WritingCallbackFulfillmentBudgetV1,
        _ResearchGraphContinuationProvider,
    )

    with workspace_tempdir() as tmpdir:
        tmp = Path(tmpdir)
        runtime, checkpoint = _research_checkpoint(tmp)
        fact = type(
            "Fact",
            (),
            {
                "fact_id": "fact:recompiled",
                "validation_status": "supported",
                "subject": "norm",
                "predicate": "uses",
                "object": "mean",
                "direct_span_ids": ("span:compute.py:10:12",),
                "relation_span_ids": (),
                "canonical_identity": "",
            },
        )()
        fingerprint = canonical_fact_fingerprint(fact)
        request = WritingResearchRequestV1(
            request_id="request:same-fp",
            section_id="MA-S1",
            argument_unit_id="MA-S1:unit",
            missing_rhetorical_move="implementation_realization",
            exact_question="How is normalization applied?",
            required_authority_lane="executable_hard",
            candidate_symbols_or_terms=("normalize",),
            baseline_span_ids=("span:compute.py:1:2",),
            baseline_fact_fingerprints=(fingerprint,),
            mandatory_missing_slots=("relation",),
            priority="high",
        )
        provider = _ResearchGraphContinuationProvider(
            runtime=runtime,
            research_stage_checkpoint=checkpoint,
            facts=None,
            plan=None,
            concept_cards=None,
            callback_root=tmp / "callbacks",
            budget=WritingCallbackFulfillmentBudgetV1(max_tool_turns_per_request=5),
            artifact_paths={},
        )
        report = provider._owning_validator_report(
            request=request,
            obligation_id="callback:request:same-fp",
            compiled=type(
                "Compiled",
                (),
                {
                    "packet_set": type("Packets", (), {"packets": [type("P", (), {"packet_id": "pkt:1"})()]})(),
                    "fact_set": type("Facts", (), {"facts": [fact]})(),
                    "claim_set": type(
                        "Claims",
                        (),
                        {
                            "claims": [
                                type(
                                    "Claim",
                                    (),
                                    {
                                        "claim_id": "claim:new",
                                        "status": "supported",
                                        "covers_obligation_ids": (
                                            "callback:request:same-fp",
                                        ),
                                    },
                                )(),
                            ],
                        },
                    )(),
                },
            )(),
            baseline_spans={"span:compute.py:1:2"},
        )
        assert report["validated"] is False
        assert "no_canonical_information_gain" in report["reasons"]
