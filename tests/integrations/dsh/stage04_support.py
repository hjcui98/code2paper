"""Actual durable facade/worker; UNIT projection is not V01 wire evidence."""
from dataclasses import asdict

from code2paper.agentic.authoring_execution_identity import capture_execution_composition
from code2paper.agentic.digest import canonical_json_bytes, digest_json
from code2paper.agentic.unified_context_compiler import build_run_invocation_budget_envelope_v1, measure_unified_tokens
from code2paper.agentic.unified_context_models import conservative_token_meter
from code2paper.integrations.dsh.artifacts import ArtifactStore, TaskScope
from code2paper.integrations.dsh.facade import ControlledHostContext, WriterFacade
from code2paper.integrations.dsh.task_store import TaskStore, SerialBackendAdmission
from code2paper.integrations.dsh.protocol import MAX_FRAME_BYTES
from code2paper.integrations.dsh.worker import rpc_schema_digest
from .fixtures import legacy_fixture_builder as builder
from .fixtures.completed_formalizer_fixture import build_fixture
from .stage03_support import ROOT, unit_projection


def durable_material(tmp_path, spec, *, prepare_contract=True, scope=None, wall_seconds=120, material_sink=None,
                     page_kind='technical', profile_overrides=None, workflow_version='writer-single-request/1',
                     epoch_limits=None):
    """When unprepared, return actual input in projection slot for C00 capture."""
    scope = scope or TaskScope("execution:stage04-unit", "task:writer", 0)
    spec.effective_config.update(options={**spec.effective_config.get("options",{}),"maxTokens":4096},
        backend_state_root=str(tmp_path / "backend"),
        backend_resource_key=spec.effective_config.get("backend_resource_key","provider:unit-test"))
    composition = capture_execution_composition(spec,engine_root=ROOT)
    identity = {key:digest_json(key) for key in ("engine_digest","target_digest","intent_digest","claims_digest",
        "profile_digest","model_digest","validator_digest","composition_digest","renderer_digest","tokenizer_digest")}
    identity.update(engine_digest=composition["engine_digest"],validator_digest=composition["validator_digest"],
        composition_digest=composition["composition_digest"],renderer_digest=composition["files"]["renderer"]["digest"],
        tokenizer_digest=composition["files"]["tokenizer"]["digest"])
    profile = builder._budget_profile()
    if profile_overrides:
        profile.update(profile_overrides)
    model = {"model":spec.effective_config.get("model"),"options":spec.effective_config["options"],
        "capabilities":{"context_tokens":131072},"authority":"controlled_offline_fixture"}
    identity.update(profile_digest=digest_json(profile),model_digest=digest_json(model))
    envelope = build_run_invocation_budget_envelope_v1(profile_budget=profile,
        model_capabilities={"context_tokens":131072}, run_digest=digest_json(scope.execution_id),
        profile_digest=identity["profile_digest"], model_identity_digest=identity["model_digest"])
    material = {}
    if page_kind == 'technical':
        build_fixture(material_sink=material,require_atom_targets=True,budget_envelope=envelope)
    elif page_kind == 'author':
        from .fixtures.author_page_fixture import build_fixture as build_author
        build_author(material_sink=material,budget_envelope=envelope)
    else:
        raise ValueError('unknown_offline_page_kind')
    target_digest=material["archive"].source_manifest_digest if page_kind == 'technical' else digest_json({
        'controlled_source_archive':material['archive'].content_digest,
        'original_source_manifest':material['archive'].source_manifest_digest})
    identity.update(target_digest=target_digest,
        intent_digest=digest_json(material["narrative"]),claims_digest=digest_json(material["section"].prompt_payload))
    if material_sink is not None:
        material_sink.update(material,profile=profile,model=model,identity=identity)
    context = ControlledHostContext(scope=scope,snapshot_digest=material["archive"].content_digest,content_revision=1,fence=0,
        caller="host:stage04",child_id="child:one",session_id="session:one",turn_id="turn:one",step_id="step:one",
        tool_call_id="tool:one",request_id="request:unreserved",claim_mode="dsh-durable-claim/1")
    store = ArtifactStore(tmp_path / "run",scope)
    facade = WriterFacade(store=store,context=context,composition_spec=spec,composition=composition,engine_root=ROOT,
        request_meter=lambda raw:measure_unified_tokens(raw.decode(),meter=conservative_token_meter()),
        task_store=TaskStore(store.root,scope),backend_admission=SerialBackendAdmission(tmp_path / "backend",spec.effective_config["backend_resource_key"]))
    limits = dict(max_model_requests=1,max_input_tokens=131072,max_output_tokens=4096,max_tool_calls=0,max_wall_seconds=wall_seconds)
    if epoch_limits is not None:
        limits=epoch_limits
    frozen = facade.freeze_input(**{key:material[key] for key in ("section","page","narrative","manifest","plan","formalizer")},
        identity=identity,epoch_limits=limits,workflow_version=workflow_version)
    input_ref = facade.render_input(frozen,cap=4096)
    projection = unit_projection(facade,input_ref) if prepare_contract else input_ref
    contract = facade.prepare(frozen,cap=4096,project=lambda _:projection) if prepare_contract else None
    budget_ref = store.put_json(envelope)
    context_json = asdict(context)
    context_json.pop("scope")
    bootstrap = tmp_path / "bootstrap.json"
    bootstrap.write_bytes(canonical_json_bytes({"artifact_root":str(store.root),"engine_root":str(ROOT),"scope":asdict(scope),
        "context":context_json,"composition_spec":{"files":{key:str(path) for key,path in spec.files.items()},
            "trees":{key:str(path) for key,path in spec.trees.items()},"effective_config":dict(spec.effective_config),"upstream_source_sha":None},
        "composition":composition,"meter":conservative_token_meter().model_dump(mode="json")}))
    return facade,contract,frozen,projection,budget_ref,bootstrap


def start_worker(bootstrap,facade):
    from .test_worker_protocol import Child
    child=Child(bootstrap)
    response=child.call("initialize",dict(protocol_version="c2p-dsh/1",schema_digest=rpc_schema_digest(),
        validator_digest=facade.composition["validator_digest"],max_frame_bytes=MAX_FRAME_BYTES))
    assert "result" in response,response
    return child


def prepare_and_claim(child,facade,contract,frozen,projection):
    params=asdict(facade.context.scope)
    result=child.call("task.prepare",{**params,"frozen_ref":frozen.model_dump(mode="json"),
        "projection_ref":facade.store.put_json(projection).model_dump(mode="json"),"cap":4096})
    assert "result" in result,result
    claim=child.call("task.claim",{**params,"owner":"host:stage04"})["result"]
    bound=child.call("task.bind",{**params,"claim":claim,"child_id":facade.context.child_id,"session_id":facade.context.session_id})
    assert "result" in bound,bound
    return params,claim,result["result"]
