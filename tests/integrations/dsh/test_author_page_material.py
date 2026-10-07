"""Local compiler/parser/frozen-material checks; no DSH provider acceptance."""

import copy
import json
import socket
from dataclasses import asdict, replace

import pytest

from code2paper.agentic.authoring_execution_identity import capture_execution_composition
from code2paper.agentic.digest import digest_bytes
from code2paper.integrations.dsh.artifacts import ArtifactStore, TaskScope
from code2paper.integrations.dsh.facade import ControlledHostContext, WriterFacade
from code2paper.integrations.dsh.protocol import ProtocolError
from code2paper.integrations.dsh.writer_contract import ArtifactRefV1
from code2paper.llm.client import LLMClient, LLMResponse
from code2paper.llm.section_writer import parse_publication_writer_response, assess_publication_content_acceptance

from .fixtures import legacy_fixture_builder as b
from .fixtures.author_page_fixture import build_fixture
from .test_composition_identity import ROOT, composition


@pytest.fixture(autouse=True)
def no_network_or_model(monkeypatch):
    def blocked(*_args, **_kwargs):
        raise AssertionError("author material tests must not send network/model requests")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(LLMClient, "complete", blocked)


def test_original_compiler_material_and_budget_are_preserved():
    envelope = b._budget_envelope()
    material = {}
    result = build_fixture(material_sink=material, budget_envelope=envelope)
    assert {"section", "page", "narrative", "manifest", "plan", "formalizer",
            "writer_raw", "archive", "budget_envelope"}.issubset(material)
    assert material["budget_envelope"] is envelope
    assert material["plan"].envelope_digest == envelope.content_digest
    archive, obligations = b._evidence_archive()
    narrative = b._narrative_plan(archive)
    manifest, plan, sections = b._writer_material(archive, obligations, narrative, envelope)
    assert material["archive"] == archive
    assert material["narrative"] == narrative
    assert material["manifest"] == manifest
    assert material["plan"] == plan
    technical, = (s for s in sections if s.section_id == b.LEGAL_SECTION_ID)
    assert b.required_targets_from_plan_row(b._page_paragraph_rows(technical)[0])["detail"]
    assert any(p.atom_ids for p in material["manifest"].pages)
    assert obligations["mech_rescale"][0].obligation_id == "ob:rescale"
    assert result["dsh_provider_acceptance"] == "not_run"
    assert not result["writer"]["verified"]["global_verified_complete"]


def test_author_page_zero_task_execution_and_raw_provider_answer():
    material = {}
    result = build_fixture(material_sink=material)
    assert not material["page"].atom_ids
    assert not material["section"].prompt_payload["formula_packages"]
    assert not material["section"].prompt_payload["formula_obligations"]
    assert not material["formalizer_plan"].invocations
    execution = material["formalizer"]
    assert execution.plan_digest == material["formalizer_plan"].content_digest
    assert execution.actual_main_calls == execution.actual_repair_calls == execution.planned_main_invocations == 0
    assert not execution.receipts and not execution.accepted_packages
    assert not execution.task_failures and not execution.assertion_failures
    provider = b.offline_provider_response(material["section"], material["request"])
    assert material["writer_raw"] == provider.text == result["writer"]["offline_response"]["raw_text"]
    parsed = parse_publication_writer_response(provider, request=material["request"], private_section=material["section"])
    accepted, metrics = assess_publication_content_acceptance(material["section"], parsed)
    assert accepted and not parsed.blocked_reason
    assert metrics["required_atom_count"] == metrics["required_target_count"] == 0
    assert metrics["valid_paragraph_count"] == 1


@pytest.mark.parametrize("mutation", ["heading_only", "extra_paragraph"])
def test_no_atom_author_page_still_requires_valid_content(mutation):
    material = {}
    build_fixture(material_sink=material)
    payload = json.loads(material["writer_raw"])
    if mutation == "heading_only":
        payload["paragraphs"][0]["paragraph_markdown"] = "# Motivation"
    else:
        extra = copy.deepcopy(payload["paragraphs"][0])
        extra["paragraph_id"] = "not-in-frozen-plan"
        payload["paragraphs"].append(extra)
    raw = json.dumps(payload)
    response = LLMResponse(text=raw, response_hash=digest_bytes(raw.encode()), finish_reason="stop")
    parsed = parse_publication_writer_response(response, request=material["request"], private_section=material["section"])
    accepted, metrics = assess_publication_content_acceptance(material["section"], parsed)
    assert parsed.blocked_reason or not accepted
    assert parsed.blocked_reason or metrics["failures"]


def test_original_facade_freezes_rebuilds_and_checks_author_dependencies(tmp_path, composition):
    material = {}
    build_fixture(material_sink=material)
    scope = TaskScope("execution:author-material-unit", "task:author-material", 0)
    context = ControlledHostContext(
        scope=scope, snapshot_digest=digest_bytes(b"author-material-unit"), content_revision=1,
        fence=0, caller="controlled-host-test", child_id="child", session_id="session",
        turn_id="turn", step_id="step", tool_call_id="tool", request_id="request",
    )
    captured = capture_execution_composition(composition, engine_root=ROOT)
    facade = WriterFacade(store=ArtifactStore(tmp_path / "run", scope), context=context,
                          composition_spec=composition, composition=captured, engine_root=ROOT)
    identity = {key: digest_bytes(key.encode()) for key in (
        "engine_digest", "target_digest", "intent_digest", "claims_digest", "profile_digest",
        "model_digest", "validator_digest", "composition_digest", "renderer_digest", "tokenizer_digest")}
    identity.update({key: captured[key] for key in ("engine_digest", "validator_digest", "composition_digest")})
    identity.update(renderer_digest=captured["files"]["renderer"]["digest"],
                    tokenizer_digest=captured["files"]["tokenizer"]["digest"])
    frozen_keys = ("section", "page", "narrative", "manifest", "plan", "formalizer")
    arguments = {key: material[key] for key in frozen_keys}
    limits = dict(max_model_requests=1, max_input_tokens=131072, max_output_tokens=4096,
                  max_tool_calls=0, max_wall_seconds=120)
    frozen_ref = facade.freeze_input(**arguments, identity=identity, epoch_limits=limits)
    frozen = facade.check_frozen_current(frozen_ref)
    assert facade.store.read_json(ArtifactRefV1.model_validate(frozen["refs"]["section"])) == json.loads(json.dumps(asdict(material["section"])))
    altered = replace(material["section"], heading="Uncompiled heading")
    with pytest.raises(ProtocolError, match="private_input_rebuild_mismatch"):
        facade.freeze_input(**{**arguments, "section": altered}, identity=identity, epoch_limits=limits)
    page_ref = frozen["refs"]["page"]
    ref = ArtifactRefV1.model_validate(page_ref)
    # Corrupt an immutable dependency: original artifact reader must fail closed.
    path = facade.store.directory / ref.artifact_id.split(":")[1]
    path.write_bytes(b"corrupt")
    with pytest.raises(ProtocolError, match="artifact_bytes_mismatch"):
        facade.check_frozen_current(frozen_ref)
