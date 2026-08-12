"""Package F tests: autonomous Writer-callback fulfillment/resume loop."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from code2paper.agentic.autonomous_method_agent import build_product_research_runtime
from code2paper.agentic.evidence_compiler_v3 import CodeFactSetV1, CodeFactV1
from code2paper.agentic.method_argument_models import (
    WritingResearchCallbackArtifactV1,
    WritingResearchCallbackBundleV1,
    WritingResearchRequestV1,
)
from code2paper.agentic.research_models import ResearchToolCallV1
from code2paper.agentic.research_tools import (
    RESEARCH_TOOL_KINDS,
    ResearchToolContext,
    execute_research_tool,
)
from code2paper.agentic.writing_callback_fulfillment import (
    WritingCallbackFulfillmentBudgetV1,
    WritingCallbackFulfillmentResultV1,
    fulfill_and_resume_writing_callbacks,
)
from code2paper.agentic.writer_research_router import (
    WritingResearchRouteV1,
    route_writing_research_request,
)
from tests.tempdir_support import workspace_tempdir


ROOT = Path(__file__).resolve().parents[1]
TOY_PROJECT = ROOT / "tests" / "fixtures" / "toy_train_project"


def _request(*, request_id: str = "request:unit:1", symbol: str = "train") -> WritingResearchRequestV1:
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


def _runtime(tmp_path: Path, ctx: ResearchToolContext) -> object:
    """A minimal runtime object exposing repo_snapshot + tool_context()."""

    return build_product_research_runtime(
        repo_path=TOY_PROJECT,
        author_intent_path=None,
        claims=None,
        run_id="callback-fulfillment-test",
        artifact_root=tmp_path / "artifacts" / "research_tool_data",
    )


def _real_span_id(ctx: ResearchToolContext, symbol: str) -> str:
    call = ResearchToolCallV1(
        tool_call_id="tc-seed",
        tool_name="read_code_span",
        tool_kind=RESEARCH_TOOL_KINDS.get("read_code_span", "other"),
        obligation_id="obl-test",
        goal="find seed span",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        arguments={"path": "train.py", "start_line": 1, "end_line": 0},
    )
    observation = execute_research_tool(ctx, call)
    assert observation.status == "success", observation.error_message
    assert observation.exact_span_ids, "seed span lookup returned no spans"
    return observation.exact_span_ids[0]


def _fact_set(*span_ids: str) -> CodeFactSetV1:
    return CodeFactSetV1(
        schema_version="1.0",
        producer_version="code2paper-evidence-compiler-v3",
        repo_snapshot_id="repo:test",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        facts=[
            CodeFactV1(
                fact_id="fact-test-1",
                subject="sym:trainer",
                predicate="calls",
                object="train_step",
                scope="sym:trainer",
                direct_span_ids=list(span_ids),
                exact_source_digest="sha256:source",
                canonical_identity="sha256:fact",
                validation_status="supported",
            )
        ],
        content_digest="sha256:facts",
    )


def test_route_open_executable_request_to_repository_tools() -> None:
    request = _request()
    route = route_writing_research_request(request)
    assert isinstance(route, WritingResearchRouteV1)
    assert route.owner == "repository_tools"
    assert route.resume_section_only is True


def test_repository_callback_provider_writes_digest_pinned_file_backed_artifact() -> None:
    from code2paper.agentic.writing_callback_fulfillment import (
        _BudgetedRepositoryCallbackProvider,
    )

    with workspace_tempdir() as tmpdir:
        tmp = Path(tmpdir)
        snapshot = _runtime(tmp, None).repo_snapshot
        ctx = ResearchToolContext(repo_snapshot=snapshot)
        runtime = _runtime(tmp, ctx)
        span_id = _real_span_id(ctx, "train")
        facts = _fact_set(span_id)
        budget = WritingCallbackFulfillmentBudgetV1()
        provider = _BudgetedRepositoryCallbackProvider(
            runtime=runtime,
            facts=facts,
            plan=None,
            callback_root=tmp / "artifacts" / "06_authoring",
            budget=budget,
        )
        raw = provider(_request(symbol="train"))
        assert raw is not None
        artifact = WritingResearchCallbackArtifactV1.model_validate(raw)
        assert artifact.artifact_id.startswith("writing-callback:")
        assert artifact.validated is True
        assert artifact.authority_lane == "executable_hard"
        # The artifact must be file-backed with a verified digest, resolved
        # relative to the callback bundle's directory (06_authoring).
        artifact_file = (tmp / "artifacts" / "06_authoring" / artifact.artifact_ref).resolve()
        assert artifact_file.is_file()
        payload = json.loads(artifact_file.read_text(encoding="utf-8"))
        assert payload["summary_for_writer"]
        assert "fact-test-1" in payload["matched_fact_ids"]
        assert artifact.artifact_digest == "sha256:" + __import__("hashlib").sha256(
            artifact_file.read_bytes()
        ).hexdigest()


def test_repository_callback_provider_leaves_unmatched_request_pending() -> None:
    from code2paper.agentic.writing_callback_fulfillment import (
        _BudgetedRepositoryCallbackProvider,
    )

    with workspace_tempdir() as tmpdir:
        tmp = Path(tmpdir)
        runtime = _runtime(tmp, None)
        ctx = ResearchToolContext(repo_snapshot=runtime.repo_snapshot)
        facts = _fact_set("span:does-not-exist:1:2")
        budget = WritingCallbackFulfillmentBudgetV1(max_tool_turns_per_request=3)
        provider = _BudgetedRepositoryCallbackProvider(
            runtime=runtime,
            facts=facts,
            plan=None,
            callback_root=tmp / "artifacts" / "06_authoring",
            budget=budget,
        )
        raw = provider(_request(symbol="train", request_id="request:nomatch"))
        assert raw is None


def test_fulfillment_loop_fulfills_and_resumes_affected_section() -> None:
    with workspace_tempdir() as tmpdir:
        tmp = Path(tmpdir)
        runtime = _runtime(tmp, None)
        ctx = ResearchToolContext(repo_snapshot=runtime.repo_snapshot)
        span_id = _real_span_id(ctx, "train")
        facts = _fact_set(span_id)
        bundle_path = tmp / "artifacts" / "06_authoring" / "writing_research_callback_artifacts_v1.json"
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        request = _request()
        bundle = WritingResearchCallbackBundleV1(requests=(request,))
        bundle_path.write_text(bundle.model_dump_json(indent=2) + "\n", encoding="utf-8")

        resume_calls: list[dict] = []
        writer_paths = {
            "writing_research_callback_artifacts_v1": str(bundle_path),
            "publication_section_checkpoint_v1": str(tmp / "artifacts" / "06_authoring" / "publication_section_checkpoint_v1.json"),
        }

        def _fake_writer(out_root, artifact_paths, llm_config, llm_caller=None,
                         resume_section_ids=(), research_callback_artifacts=None,
                         **kwargs):
            if resume_section_ids:
                resume_calls.append({
                    "resume_section_ids": tuple(resume_section_ids),
                    "callback_artifacts": sorted(research_callback_artifacts or {}),
                })
            class _Result:
                status = "success" if resume_section_ids else "incomplete"
                blocked_reason = ""
            return _Result(), writer_paths

        from code2paper.agentic import writing_callback_fulfillment as module

        with patch.object(module, "run_publication_method_writer", _fake_writer), \
             patch.object(module, "_load_facts", return_value=facts):
            new_paths, status, reason, result = fulfill_and_resume_writing_callbacks(
                runtime=runtime,
                out_root=tmp,
                artifact_paths={},
                writer_paths=writer_paths,
                llm_config=None,
                budget=WritingCallbackFulfillmentBudgetV1(max_callback_rounds=2),
            )

        assert isinstance(result, WritingCallbackFulfillmentResultV1)
        assert result.local_requests_seen == 1
        assert result.local_requests_fulfilled == 1
        assert result.resumed_section_ids == ("MA-S1",)
        assert result.stopped_reason == "writer_success"
        assert resume_calls
        assert resume_calls[0]["resume_section_ids"] == ("MA-S1",)
        assert "request:unit:1" in resume_calls[0]["callback_artifacts"]
        # The fulfilled bundle is persisted.
        updated = WritingResearchCallbackBundleV1.model_validate_json(bundle_path.read_text())
        assert updated.requests[0].status == "fulfilled"
        assert updated.requests[0].fulfilled_artifact_ids


def test_fulfillment_loop_stops_with_no_open_local_requests() -> None:
    with workspace_tempdir() as tmpdir:
        tmp = Path(tmpdir)
        runtime = _runtime(tmp, None)
        bundle_path = tmp / "artifacts" / "06_authoring" / "writing_research_callback_artifacts_v1.json"
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        bundle = WritingResearchCallbackBundleV1(requests=(
            _request().model_copy(update={"status": "blocked"}),
        ))
        bundle_path.write_text(bundle.model_dump_json(indent=2) + "\n", encoding="utf-8")
        from code2paper.agentic import writing_callback_fulfillment as module

        with patch.object(module, "_load_facts", return_value=None):
            _paths, _status, _reason, result = fulfill_and_resume_writing_callbacks(
                runtime=runtime,
                out_root=tmp,
                artifact_paths={},
                writer_paths={"writing_research_callback_artifacts_v1": str(bundle_path)},
                llm_config=None,
                budget=WritingCallbackFulfillmentBudgetV1(),
            )
        assert result.local_requests_seen == 0
        assert result.local_requests_fulfilled == 0
        assert result.stopped_reason == "no_open_requests"


def test_external_author_request_stays_queued_and_does_not_resume() -> None:
    from code2paper.agentic import writing_callback_fulfillment as module

    with workspace_tempdir() as tmpdir:
        tmp = Path(tmpdir)
        runtime = _runtime(tmp, None)
        bundle_path = tmp / "artifacts" / "06_authoring" / "writing_research_callback_artifacts_v1.json"
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        request = _request(
            request_id="request:author:1",
        ).model_copy(update={"required_authority_lane": "author_attested"})
        bundle = WritingResearchCallbackBundleV1(requests=(request,))
        bundle_path.write_text(bundle.model_dump_json(indent=2) + "\n", encoding="utf-8")

        with patch.object(module, "_load_facts", return_value=None):
            _paths, _status, _reason, result = fulfill_and_resume_writing_callbacks(
                runtime=runtime,
                out_root=tmp,
                artifact_paths={},
                writer_paths={"writing_research_callback_artifacts_v1": str(bundle_path)},
                llm_config=None,
                budget=WritingCallbackFulfillmentBudgetV1(),
            )
        assert result.local_requests_seen == 0
        assert result.external_requests_seen == 1
        assert result.resumed_section_ids == ()
        assert result.stopped_reason == "no_open_local_requests"
        # The request is untouched and still open (queued for the author).
        updated = WritingResearchCallbackBundleV1.model_validate_json(bundle_path.read_text())
        assert updated.requests[0].status == "open"


def test_formalization_request_loads_typed_result_and_resumes() -> None:
    from code2paper.agentic.formalization_agent import FormalizationResultV1

    with workspace_tempdir() as tmpdir:
        tmp = Path(tmpdir)
        runtime = _runtime(tmp, None)
        bundle_path = tmp / "artifacts" / "06_authoring" / "writing_research_callback_artifacts_v1.json"
        formalization_path = tmp / "artifacts" / "06_authoring" / "formalization_result_v1.json"
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        request = _request(request_id="request:formal:1").model_copy(update={
            "required_authority_lane": "formal_derivation",
            "missing_rhetorical_move": "equation_or_derivation",
            "candidate_symbols_or_terms": ("score",),
        })
        bundle = WritingResearchCallbackBundleV1(requests=(request,))
        bundle_path.write_text(bundle.model_dump_json(indent=2) + "\n", encoding="utf-8")
        formalization = FormalizationResultV1(
            repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
            project_tree_hash=runtime.repo_snapshot.project_tree_hash,
            fact_digest="sha256:facts",
        )
        formalization_path.write_text(
            formalization.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        writer_paths = {
            "writing_research_callback_artifacts_v1": str(bundle_path),
            "publication_section_checkpoint_v1": str(
                tmp / "artifacts" / "06_authoring" / "publication_section_checkpoint_v1.json"
            ),
        }
        resume_calls: list[dict] = []

        def _fake_writer(out_root, artifact_paths, llm_config, llm_caller=None,
                         resume_section_ids=(), research_callback_artifacts=None,
                         **kwargs):
            resume_calls.append({
                "resume_section_ids": tuple(resume_section_ids),
                "callback_artifacts": research_callback_artifacts or {},
            })
            class _Result:
                status = "success"
                blocked_reason = ""
            return _Result(), writer_paths

        from code2paper.agentic import writing_callback_fulfillment as module

        with patch.object(module, "run_publication_method_writer", _fake_writer):
            _paths, status, reason, result = fulfill_and_resume_writing_callbacks(
                runtime=runtime,
                out_root=tmp,
                artifact_paths={"formalization_result_v1": str(formalization_path)},
                writer_paths=writer_paths,
                llm_config=None,
                budget=WritingCallbackFulfillmentBudgetV1(max_callback_rounds=1),
            )

        assert status == "success"
        assert reason == ""
        assert result.local_requests_seen == 1
        assert result.local_requests_fulfilled == 1
        assert result.resumed_section_ids == ("MA-S1",)
        assert resume_calls[0]["resume_section_ids"] == ("MA-S1",)
        artifact = resume_calls[0]["callback_artifacts"]["request:formal:1"][0]
        assert artifact.authority_lane == "formal_derivation"
        assert artifact.artifact_digest == formalization.content_digest


def test_fulfillment_budget_is_progress_driven() -> None:
    from code2paper.agentic import writing_callback_fulfillment as module

    with workspace_tempdir() as tmpdir:
        tmp = Path(tmpdir)
        runtime = _runtime(tmp, None)
        ctx = ResearchToolContext(repo_snapshot=runtime.repo_snapshot)
        facts = _fact_set("span:never-matched:9:9")
        bundle_path = tmp / "artifacts" / "06_authoring" / "writing_research_callback_artifacts_v1.json"
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        request = _request(request_id="request:budget:1")
        bundle = WritingResearchCallbackBundleV1(requests=(request,))
        bundle_path.write_text(bundle.model_dump_json(indent=2) + "\n", encoding="utf-8")
        with patch.object(module, "_load_facts", return_value=facts):
            _paths, _status, _reason, result = fulfill_and_resume_writing_callbacks(
                runtime=runtime,
                out_root=tmp,
                artifact_paths={},
                writer_paths={"writing_research_callback_artifacts_v1": str(bundle_path)},
                llm_config=None,
                budget=WritingCallbackFulfillmentBudgetV1(max_callback_rounds=2),
            )
        assert result.local_requests_fulfilled == 0
        assert result.stopped_reason in {"no_progress", "budget_exhausted"}
