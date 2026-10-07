"""Controlled test scope and real compiler inputs, not a production claim."""
from dataclasses import asdict
from pathlib import Path

from code2paper.agentic.authoring_execution_identity import capture_execution_composition
from code2paper.agentic.digest import canonical_json_bytes,digest_bytes,digest_json
from code2paper.integrations.dsh.artifacts import ArtifactStore,TaskScope
from code2paper.integrations.dsh.facade import ControlledHostContext,WriterFacade
from code2paper.integrations.dsh.writer_contract import seal_contract,terminal_schema
from code2paper.agentic.page_contract_recheck import author_surface_digest,binding_contract_digest
from .fixtures.completed_formalizer_fixture import build_fixture

ROOT=Path(__file__).resolve().parents[3]


def local_test_facade(tmp_path,spec,*,native_tool_choice=None,provider_options=None):
    scope=TaskScope("execution:stage03-test","task:writer",0)
    context=ControlledHostContext(scope=scope,snapshot_digest=digest_bytes(b"snapshot"),content_revision=1,fence=0,
        caller="controlled-host-test",child_id="child-1",session_id="session-1",turn_id="turn-1",step_id="step-1",tool_call_id="tool-1",request_id="request-1")
    spec.effective_config["options"]={"maxTokens":4096}
    if provider_options is not None:
        spec.effective_config["options"].update(provider_options)
    if native_tool_choice is not None:
        spec.effective_config["options"]["nativeToolChoice"] = native_tool_choice
    composition=capture_execution_composition(spec,engine_root=ROOT)
    facade=WriterFacade(store=ArtifactStore(tmp_path/"run",scope),context=context,composition_spec=spec,composition=composition,engine_root=ROOT)
    material={};build_fixture(material_sink=material,require_atom_targets=True)
    identity={key:digest_bytes(key.encode()) for key in ("engine_digest","target_digest","intent_digest","claims_digest","profile_digest","model_digest","validator_digest","composition_digest","renderer_digest","tokenizer_digest")}
    identity.update(engine_digest=composition["engine_digest"],validator_digest=composition["validator_digest"],composition_digest=composition["composition_digest"],renderer_digest=composition["files"]["renderer"]["digest"],tokenizer_digest=composition["files"]["tokenizer"]["digest"])
    limits=dict(max_model_requests=1,max_input_tokens=131072,max_output_tokens=4096,max_tool_calls=0,max_wall_seconds=120)
    frozen_ref=facade.freeze_input(**{key:material[key] for key in ("section","page","narrative","manifest","plan","formalizer")},identity=identity,epoch_limits=limits)
    # Fully bound LOCAL UNIT graph. These controlled fixtures are not observed
    # C00 provider evidence; real DSH/pi-ai capture is covered by joint drivers.
    from code2paper.agentic.unified_context_compiler import measure_unified_tokens
    from code2paper.agentic.unified_context_models import conservative_token_meter
    facade.request_meter=lambda raw:measure_unified_tokens(raw.decode(),meter=conservative_token_meter())
    input=facade.render_input(frozen_ref,cap=4096)
    projection=unit_projection(facade,input)
    contract=facade.prepare(frozen_ref,cap=4096,project=lambda _:projection)
    return facade,contract,material,frozen_ref


def observed_output(facade,raw,**updates):
    from code2paper.integrations.dsh.result_ingest import OutputEnvelopeV1
    scope=facade.context.scope
    raw_ref=facade.store.put(raw,media_type="application/octet-stream")
    from code2paper.integrations.dsh.protocol import strict_json_loads
    normalized=facade.store.put(canonical_json_bytes(strict_json_loads(raw)),media_type="application/octet-stream")
    values=dict(schema_version="OutputEnvelopeV1",execution_id=scope.execution_id,task_id=scope.task_id,task_epoch=scope.task_epoch,
        **{key:getattr(facade.context,key) for key in ("child_id","session_id","turn_id","step_id","tool_call_id","request_id")},
        source="adapter_tool_arguments_delta",arguments_complete=True,provider_http=dict(status="not_observed",ref=None),
        adapter_arguments=dict(status="observed",ref=raw_ref),normalized_arguments=dict(status="observed",ref=normalized),stop_reason=None,usage=None)
    values.update(updates)
    return OutputEnvelopeV1(**values)


def terminal_raw(material):
    import json
    return canonical_json_bytes({"schema_version":"WriterTaskResultV1","result":{"outcome":"draft","draft":json.loads(material["writer_raw"])}})


def unit_projection(facade,input,*,context_tokens=131072):
    """A deterministic structural test double; never an observed-wire claim."""
    from code2paper.integrations.dsh.writer_contract import seal_projection
    expected={"input_digest":input.input_digest,"renderer_digest":input.renderer_digest,
        "composition_digest":input.composition_digest,"model":input.model,"effective_options":input.effective_options,
        "post_clamp_max_output_tokens":input.post_clamp_max_output_tokens,
        "system_text":input.writer_request["prompt"]+"\n\n"+input.terminal_instruction,
        "user_text":input.task_view_json,"tools":[{"name":"c2p_terminal",
            "description":"Return the single WriterTaskResultV1 terminal candidate. No domain acceptance is granted.",
            "parameters":input.native_terminal_schema}]}
    loop={"messages":[{"role":role,"content":[{"type":"text","text":expected[key]}]}
        for role,key in (("system","system_text"),("user","user_text"))],"tools":expected["tools"],
        "model":input.model,"maxTokens":input.post_clamp_max_output_tokens}
    if "provider" in input.effective_options: loop["provider"]=input.effective_options["provider"]
    provider={"messages":[{"role":row["role"],"content":row["content"][0]["text"]} for row in loop["messages"]],
        "tools":[{"type":"function","function":{**tool,
            **({} if input.effective_options.get('nativeToolSchemaMode')=='server-default' else {"strict":False})
        }} for tool in expected["tools"]],
        "model":input.model,"max_tokens":input.post_clamp_max_output_tokens}
    if "temperature" in input.effective_options: provider["temperature"]=input.effective_options["temperature"]
    if input.effective_options.get('provider')=='openai' and input.effective_options.get('reasoningEffort')=='off':
        provider['chat_template_kwargs']=facade.composition['effective_config']['writer_chat_template_kwargs']
    elif "reasoningEffort" in input.effective_options: provider["reasoning_effort"]=input.effective_options["reasoningEffort"]
    if "nativeToolChoice" in input.effective_options: provider["tool_choice"]=input.effective_options["nativeToolChoice"]
    loop_ref=facade.store.put_json(loop);wire_ref=facade.store.put_json(provider)
    comparison=facade.store.put_json({"binding":expected,"loop_digest":loop_ref.bytes_digest,"provider_digest":wire_ref.bytes_digest})
    equivalence=facade.store.put_json({"schema_version":"WriterWireEquivalenceV1","input_digest":input.input_digest,
        "renderer_digest":input.renderer_digest,"composition_digest":input.composition_digest,
        "projection_material_digest":digest_json(expected),"loop_request_ref":loop_ref,"provider_wire_ref":wire_ref,
        "comparison_ref":comparison,"transport_whitelist":[]})
    tokens=facade.request_meter(facade.store.read(wire_ref))
    measurement=facade.store.put_json({"schema_version":"WriterMeasurementV1","input_digest":input.input_digest,
        "renderer_digest":input.renderer_digest,"tokenizer_digest":facade.composition["files"]["tokenizer"]["digest"],
        "meter_version":facade.composition["effective_config"]["meter_version"],"measured_input_tokens":tokens,
        "context_tokens":context_tokens,"safety_margin_tokens":512,"thinking_tokens":0,
        "post_clamp_max_output_tokens":input.post_clamp_max_output_tokens,"measured_wire_digest":wire_ref.bytes_digest})
    return seal_projection({"schema_version":"WriterWireProjectionV1","protocol_version":"c2p-dsh/1",**expected,"renderer_version":input.renderer_version,
        "task_view_digest":digest_json(input.writer_request["input_payload"]),"terminal_schema_digest":digest_json(input.terminal_schema),
        "measurement_ref":measurement,"wire_equivalence_ref":equivalence})
