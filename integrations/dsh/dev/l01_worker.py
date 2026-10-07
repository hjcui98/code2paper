"""Private L01 development bootstrap over original Worker/Facade/fee owners.

Only `tokenize` performs a non-generating model-service read. Worker RPC never
opens the network. Offline token receipts are visibly synthetic and require a
separate network namespace; they cannot authorize the live mode.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import socket
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[3]))

from code2paper.agentic.authoring_execution_identity import (
    CompositionSpecV1, capture_execution_composition, capture_engine_source_snapshot,
    capture_validator_bundle_snapshot,
)
from code2paper.agentic.digest import canonical_json_bytes, digest_bytes, digest_json
from code2paper.agentic.unified_context_compiler import build_run_invocation_budget_envelope_v1
from code2paper.integrations.dsh.artifacts import ArtifactStore, TaskScope
from code2paper.integrations.dsh.facade import ControlledHostContext, WriterFacade
from code2paper.integrations.dsh.protocol import MAX_FRAME_BYTES, ProtocolError, strict_json_loads
from code2paper.integrations.dsh.task_store import TaskStore, SerialBackendAdmission
from code2paper.integrations.dsh.worker import Worker, serve, rpc_schema_digest

MODEL = 'qwen38-27b-nvfp4'
BASE_URL = 'http://127.0.0.1:8006/v1'
METER = 'vllm-exact-dsh-wire-receipt/2'
INPUT_CAP = 32768
OUTPUT_CAP = 4096
WALL_SECONDS = 180


def read(path):
    return strict_json_loads(Path(path).read_bytes(), max_bytes=32 << 20)


def spec_from(value):
    return CompositionSpecV1(files={k: Path(v) for k,v in value['files'].items()},
        trees={k: Path(v) for k,v in value['trees'].items()},
        effective_config=value['effective_config'], upstream_source_sha=value.get('upstream_source_sha'))


def reasoning_mode(runtime_profile):
    """Resolve the frozen L01 provider mode; omission is never explicit off."""
    provider = runtime_profile['provider_config']['providers']['openai']
    mode = provider.get('reasoning')
    compat = provider.get('compat', {})
    if compat.get('supportsStrictMode') is not False:
        raise ProtocolError('l01_parameter_schema_opt_out_forbidden')
    if mode == 'off':
        if ('thinkingBudgets' in provider or compat.get('thinkingFormat') != 'chat-template'
                or compat.get('chatTemplateKwargs') != {'enable_thinking': False}
                or type(compat['chatTemplateKwargs']['enable_thinking']) is not bool):
            raise ProtocolError('l01_nonthinking_profile_invalid')
        return mode, 0
    if mode == 'low':
        budget = provider.get('thinkingBudgets', {}).get('low')
        if type(budget) is not int or budget <= 0 or 'chatTemplateKwargs' in compat:
            raise ProtocolError('l01_thinking_profile_invalid')
        return mode, budget
    raise ProtocolError('l01_reasoning_mode_invalid')


def prepare(values):
    # B01 provides a small, explicitly synthetic source and original completed
    # Formalizer material. No fixture Writer answer is exported to the model.
    from tests.integrations.dsh.fixtures.completed_formalizer_fixture import build_fixture
    from tests.integrations.dsh.fixtures.legacy_fixture_builder import _budget_profile
    if values.get('network_mode') not in {'isolated_fake','live_packet'}:
        raise ProtocolError('l01_network_mode_required')
    root = Path(values['root']).resolve()
    if root.exists():
        raise ProtocolError('l01_root_must_be_fresh')
    root.mkdir()
    engine = Path(values['engine_root']).resolve()
    scope = TaskScope('execution:l01:' + root.parent.name, 'task:writer', 0)
    runtime_profile = read(values['files']['l01_profile'])
    mode, thinking_reserve = reasoning_mode(runtime_profile)
    profile = _budget_profile()
    profile.update(max_page_input_tokens=20000, max_total_input_tokens=65536,
        max_formalizer_calls=1, max_writer_calls=1, max_realizer_calls=0,
        max_formula_repair_calls=0, max_obligations_per_page=1, thinking_token_reserve=1024,
        max_request_input_tokens_writer=INPUT_CAP, retry_reserve_input_tokens_writer=0)
    model = {'model': MODEL, 'base_url': BASE_URL, 'context_tokens': 131072,
        'authority': 'isolated_fake_qwen_wire' if values['network_mode']=='isolated_fake' else 'operator_designated_local_runtime',
        'writer_thinking_tokens':thinking_reserve,
        'options': {'provider':'openai', 'temperature':0.6, 'reasoningEffort':mode, 'maxTokens':OUTPUT_CAP},
        'unsupported_sampling_fields':['top_p','top_k'], 'equivalent_to_python_profile':False}
    native_choice = runtime_profile['provider_config']['providers']['openai'].get('toolChoice')
    if native_choice is not None:
        model['options']['nativeToolChoice'] = native_choice
    model['options']['nativeToolSchemaMode'] = 'server-default'
    effective = {'model':MODEL, 'options':model['options'], 'writer_thinking_tokens':thinking_reserve,
        'worker_version':'dsh-private-worker/1',
        'renderer_version':'native-text/1','tokenizer_version':METER,'meter_version':METER,
        'backend_state_root':str(Path(values['backend_state_root']).resolve()),
        'backend_resource_key':('isolated-fake:' if values['network_mode']=='isolated_fake' else 'openai:')+BASE_URL+'#'+MODEL}
    if mode == 'off':
        kwargs = runtime_profile['provider_config']['providers']['openai']['compat']['chatTemplateKwargs']
        effective['writer_chat_template_kwargs'] = kwargs
        model['writer_chat_template_kwargs'] = kwargs
    spec = CompositionSpecV1(files={k:Path(v) for k,v in values['files'].items()},
        trees={k:Path(v) for k,v in values['trees'].items()},effective_config=effective)
    composition = capture_execution_composition(spec,engine_root=engine)
    envelope = build_run_invocation_budget_envelope_v1(profile_budget=profile,
        model_capabilities={'context_tokens':131072},run_digest=digest_json(scope.execution_id),
        profile_digest=digest_json(profile),model_identity_digest=digest_json(model))
    material = {}
    build_fixture(material_sink=material,require_atom_targets=True,readable_atom_targets=True,budget_envelope=envelope)
    context = ControlledHostContext(scope=scope,snapshot_digest=material['archive'].content_digest,
        content_revision=1,fence=0,caller='host:l01',child_id='child:unbound',session_id='session:unbound',
        turn_id='turn:unbound',step_id='step:unbound',tool_call_id='tool:unbound',
        request_id='request:unreserved',claim_mode='dsh-durable-claim/1')
    store = ArtifactStore(root/'run',scope)
    facade = WriterFacade(store=store,context=context,composition_spec=spec,composition=composition,
        engine_root=engine,task_store=TaskStore(store.root,scope),
        backend_admission=SerialBackendAdmission(Path(effective['backend_state_root']),effective['backend_resource_key']))
    identity = {'engine_digest':composition['engine_digest'],'validator_digest':composition['validator_digest'],
        'composition_digest':composition['composition_digest'],
        'renderer_digest':composition['files']['renderer']['digest'],
        'tokenizer_digest':composition['files']['tokenizer']['digest'],
        'target_digest':material['archive'].source_manifest_digest,
        'intent_digest':digest_json(material['narrative']),
        'claims_digest':digest_json(material['section'].prompt_payload),
        'profile_digest':digest_json(profile),'model_digest':digest_json(model)}
    frozen = facade.freeze_input(**{k:material[k] for k in ('section','page','narrative','manifest','plan','formalizer')},
        identity=identity,epoch_limits=dict(max_model_requests=1,max_input_tokens=INPUT_CAP,
            max_output_tokens=OUTPUT_CAP,max_tool_calls=0,max_wall_seconds=WALL_SECONDS))
    inp = facade.render_input(frozen,cap=OUTPUT_CAP)
    bootstrap = root/'bootstrap.json'
    ctx = asdict(context);ctx.pop('scope')
    bootstrap.write_bytes(canonical_json_bytes({'artifact_root':str(store.root),'engine_root':str(engine),
        'scope':asdict(scope),'context':ctx,'composition_spec':{'files':{k:str(v) for k,v in spec.files.items()},
        'trees':{k:str(v) for k,v in spec.trees.items()},'effective_config':effective,'upstream_source_sha':None},
        'composition':composition,'meter':{'kind':METER,'receipt_path':str(root/'tokenizer-receipt.json')}}))
    return {'bootstrap':str(bootstrap),'scope':asdict(scope),'frozen_ref':frozen.model_dump(mode='json'),
        'input':inp.model_dump(mode='json'),'budget_ref':store.put_json(envelope).model_dump(mode='json'),
        'composition_digest':composition['composition_digest'],'tokenizer_digest':identity['tokenizer_digest'],
        'initialize':{'protocol_version':'c2p-dsh/1','schema_digest':rpc_schema_digest(),
            'validator_digest':composition['validator_digest'],'max_frame_bytes':MAX_FRAME_BYTES},
        'profile':profile,'model':model,'writer_thinking_tokens':thinking_reserve,
        'input_cap':INPUT_CAP,'output_cap':OUTPUT_CAP,'wall_seconds':WALL_SECONDS,
        'input_provenance':'B01 synthetic scalar source; original compiler and offline Formalizer; no fixture Writer answer',
        'inference_requests':0}


def bound_meter(path):
    def measure(wire):
        value = read(path)
        if (value.get('schema_version') != 'L01TokenizerReceiptV1' or value.get('model') != MODEL
                or value.get('base_url') != BASE_URL or value.get('meter_version') != METER
                or value.get('wire_digest') != digest_bytes(wire)
                or type(value.get('input_tokens')) is not int or not 0 < value['input_tokens'] <= INPUT_CAP):
            raise ProtocolError('l01_tokenizer_binding_invalid')
        if value.get('origin') == 'isolated_offline_placeholder':
            from code2paper.integrations.dsh.qualification import assert_offline_qualification_namespace
            assert_offline_qualification_namespace(value['parent_namespace'])
            if value['input_tokens'] != (len(wire)+3)//4:
                raise ProtocolError('l01_offline_meter_invalid')
        elif value.get('origin') != 'vllm_tokenize_exact_messages_tools':
            raise ProtocolError('l01_tokenizer_origin_invalid')
        return value['input_tokens']
    return measure


def run_worker(bootstrap):
    value = read(bootstrap)
    if value.get('meter',{}).get('kind') != METER:
        raise ProtocolError('l01_meter_required')
    scope = TaskScope(**value['scope']); spec = spec_from(value['composition_spec'])
    context = ControlledHostContext(scope=scope,**value['context'])
    store = ArtifactStore(Path(value['artifact_root']),scope)
    facade = WriterFacade(store=store,context=context,composition_spec=spec,composition=value['composition'],
        engine_root=Path(value['engine_root']),request_meter=bound_meter(value['meter']['receipt_path']),
        task_store=TaskStore(store.root,scope),backend_admission=SerialBackendAdmission(
            Path(spec.effective_config['backend_state_root']),spec.effective_config['backend_resource_key']))
    # Trusted host constructor injects the frozen wire meter. All actual claim,
    # reserve, dispatch, usage, ingest and recovery stay in the original Worker.
    facts={'schema_version':'PythonLlmRefusalSentinelV1','state':'installed',
        'probe_refused':False,'model_calls':0,'network_calls':0}
    sentinel=Path(bootstrap).parent/'python-sentinel.json'
    def flush():
        with sentinel.open('w') as stream:
            json.dump(facts,stream);stream.flush();os.fsync(stream.fileno())
    def model_refused(*a,**kw):
        facts['model_calls']+=1;flush();raise AssertionError('hidden_python_llm_refused')
    def network_refused(*a,**kw):
        facts['network_calls']+=1;flush();raise AssertionError('hidden_python_network_refused')
    from code2paper.llm.client import LLMClient
    LLMClient.complete=model_refused
    socket.socket.connect=network_refused;socket.socket.connect_ex=network_refused
    try: LLMClient.complete(None,None)
    except AssertionError: facts['probe_refused']=True
    facts['model_calls']=0;flush()
    try: serve(Worker(facade))
    finally: facts['state']='closed';flush()


def tokenizer_request(body):
    """Mirror the designated vLLM chat-template inputs, without dispatching."""
    request={'model':MODEL,'messages':body['messages'],'tools':body['tools'],
        'add_generation_prompt':True}
    kwargs=dict(body.get('chat_template_kwargs') or {})
    effort=body.get('reasoning_effort')
    if effort is not None:
        # ChatCompletionRequest.build_chat_params overrides template effort
        # from the top-level request, but preserves explicit enable_thinking.
        kwargs['reasoning_effort']=effort
        kwargs.setdefault('enable_thinking',effort != 'none')
    if kwargs: request['chat_template_kwargs']=kwargs
    return request


def action(value):
    from code2paper.integrations.dsh.writer_contract import seal_projection
    if value['action']=='namespace':
        from code2paper.integrations.dsh.qualification import assert_offline_qualification_namespace
        return assert_offline_qualification_namespace(value["parent"])
    if value['action']=='digest': return digest_json(value['value'])
    if value['action']=='seal': return seal_projection(value['value'])
    if value['action']=='budget':
        from code2paper.agentic.unified_invocation_ledger import read_run_budget_state
        return read_run_budget_state(Path(value['path']))
    if value['action']=='snapshot':
        from code2paper.agentic.unified_invocation_ledger import read_run_budget_state
        bootstrap=read(value['bootstrap']);root=Path(bootstrap['artifact_root'])
        scope=TaskScope(**bootstrap['scope']);config=bootstrap['composition_spec']['effective_config']
        try: task=TaskStore.read_persisted(root,scope)
        except ProtocolError as error: task={'readback_error':error.code}
        return {'schema_version':'L01OwnerReadbackV1','scope':scope.__dict__,'task':task,
            'budget':read_run_budget_state(root/'artifacts/06_authoring/invocations'),
            'backend':SerialBackendAdmission.read_persisted(Path(config['backend_state_root']),config['backend_resource_key']),
            'observational_only':True,'grants_execution':False}
    if value['action']=='admit':
        from code2paper.agentic.live_admission_preflight import OfflineSuiteReceiptV1
        receipt=OfflineSuiteReceiptV1.model_validate(read(value['receipt']))
        engine=capture_engine_source_snapshot(Path(value['engine_root']))
        validator=capture_validator_bundle_snapshot(Path(value['engine_root']))
        if (receipt.machine_plan.get('name')!='dsh-stage04' or receipt.machine_plan.get('candidate')!=value['candidate']
            or not engine.is_usable or engine.unstable or not validator.is_usable
            or not receipt.matches(engine,validator_bundle_digest=validator.digest,
                effective_config_digest=digest_json(receipt.machine_plan['effective_config']))):
            raise ProtocolError('l01_current_offline_receipt_required')
        return {'engine_digest':engine.source_digest,'validator_digest':validator.digest,
            'receipt_digest':digest_bytes(Path(value['receipt']).read_bytes()),'coverage_only':True,
            'model_execution_authorized':False}
    if value['action']=='tokenize':
        from code2paper.llm.tokenizer import VllmOpenAIChatTokenizer
        wire=Path(value['wire_path']).read_bytes();body=strict_json_loads(wire)
        # Preserve exact messages and tools, including their order and schema.
        # No Python Writer response_format substitution or component estimate.
        request=tokenizer_request(body)
        ids=VllmOpenAIChatTokenizer(BASE_URL,MODEL)._post(request)
        if not 0 < len(ids) <= INPUT_CAP: raise ProtocolError('l01_input_token_cap_exceeded')
        receipt={'schema_version':'L01TokenizerReceiptV1','origin':'vllm_tokenize_exact_messages_tools',
            'model':MODEL,'base_url':BASE_URL,'meter_version':METER,'wire_digest':digest_bytes(wire),
            'input_tokens':len(ids),'token_ids_digest':digest_json(ids),'tokenize_request':request}
        Path(value['receipt_path']).write_bytes(canonical_json_bytes(receipt))
        return {'input_tokens':len(ids),'receipt_digest':digest_bytes(canonical_json_bytes(receipt))}
    raise ProtocolError('l01_action_unavailable')

def main():
    # startKernelWorker uses its unchanged fixed original argv. The private
    # operator launcher selects this dev bootstrap explicitly, never a tool.
    if len(sys.argv)>2 and sys.argv[1:3]==['-m','code2paper.integrations.dsh.worker']:
        sys.argv=[sys.argv[0],*sys.argv[3:]]
    parser=argparse.ArgumentParser()
    parser.add_argument('--bootstrap',type=Path)
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--action',action='store_true')
    args=parser.parse_args()
    if args.prepare: print(canonical_json_bytes(prepare(strict_json_loads(sys.stdin.buffer.read()))).decode())
    elif args.action: print(canonical_json_bytes(action(strict_json_loads(sys.stdin.buffer.read()))).decode())
    elif args.bootstrap: run_worker(args.bootstrap)
    else: parser.error('choose --prepare or --bootstrap')

if __name__=='__main__': main()
