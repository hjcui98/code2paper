"""Original Kernel source material over a real private Worker channel."""
import json

import pytest

from code2paper.agentic.digest import canonical_json_bytes, digest_bytes
from .stage04_support import durable_material, start_worker, prepare_and_claim
from .test_composition_identity import composition
from .test_multistep_accounting import LIMITS


def test_v2_kernel_exports_complete_original_visible_input_not_a_summary(tmp_path,composition):
    facade,contract,frozen,projection,_,bootstrap=durable_material(tmp_path,composition,
        workflow_version='writer-multistep/2',epoch_limits=LIMITS)
    child=start_worker(bootstrap,facade)
    try:
        scope,claim,_=prepare_and_claim(child,facade,contract,frozen,projection)
        limits=child.call('task.limits',{**scope,'claim':claim})
        assert limits['result']['epoch_limits']==LIMITS
        ref=facade.store.put_json(contract).model_dump(mode='json')
        response=child.call('context.materials',{**scope,'contract_ref':ref})
        assert 'result' in response,response
        bundle=response['result'];material=bundle['required'][0]
        request=facade.store.read_json(contract.writer_request_ref)
        assert material['kind']=='writer_task_view'
        assert material['text']==canonical_json_bytes(request['input_payload']).decode()
        assert material['bytesDigest']==digest_bytes(material['text'].encode())
        assert json.loads(material['text'])==request['input_payload']
        assert bundle['origin_ref']==contract.writer_request_ref.model_dump(mode='json')
        assert bundle['scope']==dict(executionId=scope['execution_id'],taskId=scope['task_id'],
            epoch=scope['task_epoch'],sessionId=facade.context.session_id,revision=facade.context.content_revision,
            snapshotDigest=facade.context.snapshot_digest)
        denied=child.call('context.materials',{**scope,'contract_ref':ref,'summary':'model authored surrogate'})
        assert denied['error']['message']=='schema_invalid'
        child.call('task.cancel',{**scope,'claim':claim})
        assert child.call('context.materials',{**scope,'contract_ref':ref})['error']['message']=='task_mutation_closed'
    finally:child.close()


def test_v1_remains_explicit_single_request_and_has_no_multistep_material_capability(tmp_path,composition):
    facade,contract,frozen,projection,_,bootstrap=durable_material(tmp_path,composition)
    child=start_worker(bootstrap,facade)
    try:
        scope,claim,_=prepare_and_claim(child,facade,contract,frozen,projection)
        limits=child.call('task.limits',{**scope,'claim':claim})['result']['epoch_limits']
        assert limits['max_model_requests']==1 and 'max_tool_return_bytes' not in limits
        ref=facade.store.put_json(contract).model_dump(mode='json')
        assert child.call('context.materials',{**scope,'contract_ref':ref})['error']['message']=='multistep_contract_required'
        assert child.call('context.read_grants',{**scope,'contract_ref':ref})['error']['message']=='multistep_contract_required'
    finally:child.close()


def test_real_v2_worker_issues_only_public_navigation_with_frozen_epoch_limits(tmp_path,composition):
    from code2paper.integrations.dsh.scoped_reads import ScopedReads
    facade,contract,frozen,projection,_,bootstrap=durable_material(tmp_path,composition,
        workflow_version='writer-multistep/2',epoch_limits=LIMITS)
    child=start_worker(bootstrap,facade)
    try:
        scope,claim,_=prepare_and_claim(child,facade,contract,frozen,projection)
        params={**scope,'contract_ref':facade.store.put_json(contract).model_dump(mode='json')}
        issued=child.call('context.read_grants',params)
        assert 'result' in issued,issued
        grants=issued['result']['grants'];assert len(grants)==1
        grant=grants[0];assert grant['kind']=='navigation'
        read={**scope,'grant_id':grant['grant_id'],'offset':0,'length':16}
        observed=child.call('task.read_grant',read)['result']
        value=json.loads(observed['model_text'])
        request=facade.store.read_json(contract.writer_request_ref)
        public=canonical_json_bytes(request['input_payload'])
        assert value['text']==public[:16].decode()
        assert value['source_digest']==digest_bytes(public)
        assert value['source_digest']!=contract.private_input_ref.bytes_digest
        reads=ScopedReads(facade.task_store,facade.store,facade.current_state)
        status=reads.status(claim,session_id=facade.context.session_id)
        assert status['max_calls']==LIMITS['max_tool_calls']
        assert status['max_bytes']==LIMITS['max_tool_return_bytes']
        assert status['calls']==1 and status['delivered_bytes']==observed['delivered_bytes']
        assert child.call('context.read_grants',params)['result']['grants']==grants
        assert reads.status(claim,session_id=facade.context.session_id)==status
        # No caller-supplied span, kind, cap, ref or read-set can expand this grant.
        assert child.call('context.read_grants',{**params,'max_bytes':1000000})['error']['message']=='schema_invalid'
        assert child.call('task.read_grant',{**read,'kind':'exact_excerpt'})['error']['message']=='schema_invalid'
        child.call('task.cancel',{**scope,'claim':claim})
        assert child.call('context.read_grants',params)['error']['message']=='task_mutation_closed'
    finally:child.close()


def test_real_v2_worker_records_bad_terminal_source_before_content_parse(tmp_path,composition):
    from code2paper.agentic.digest import digest_json
    from code2paper.agentic.unified_context_models import DshInvocationEventV1
    from code2paper.agentic.unified_invocation_ledger import publish_dsh_invocation_event,read_run_budget_state
    from code2paper.integrations.dsh.epoch_tools import EpochTools
    facade,contract,frozen,projection,_,bootstrap=durable_material(tmp_path,composition,
        workflow_version='writer-multistep/2',epoch_limits=LIMITS)
    child=start_worker(bootstrap,facade)
    try:
        scope,claim,_=prepare_and_claim(child,facade,contract,frozen,projection)
        ledger=facade.store.root/'artifacts/06_authoring/invocations'
        binding=dict(invocation_id='request:unit-block-end',attempt=1,**scope,
                     claim_digest=digest_json(claim),request_digest=digest_json('unit-loop-request'),
                     contract_digest=contract.task_digest,plan_digest=digest_json('unit-plan'),consumer_role='writer')
        for kind in ('reserve','dispatch-recorded','adapter-attempt'):
            publish_dsh_invocation_event(ledger,DshInvocationEventV1(**binding,event_id='unit:'+kind,kind=kind,
                source='host-adapter' if kind=='adapter-attempt' else 'kernel',
                **(dict(reserved_input_tokens=100,reserved_output_tokens=4096) if kind=='reserve' else {})))
        raw=facade.store.put(b'not JSON',media_type='application/octet-stream')
        candidate=dict(schema_version='DshToolCandidateV2',**scope,child_id=facade.context.child_id,
            session_id=facade.context.session_id,request_id=binding['invocation_id'],tool_call_id='native:first',
            stream_index=2,name='c2p_terminal',arguments_ref=raw.model_dump(mode='json'),
            source='gated-adapter-tool-arguments-delta/2')
        params={**scope,'contract_ref':facade.store.put_json(contract).model_dump(mode='json'),'candidate':candidate}
        assert child.call('task.record_tool_candidate',params)['result']['admitted']
        candidate2={**candidate,'tool_call_id':'native:repair'}
        assert child.call('task.record_tool_candidate',{**params,'candidate':candidate2})['error']['message']=='dsh_epoch_terminal_already_consumed'
        assert EpochTools(facade.task_store,facade.store,facade.current_state).status(claim,contract)==dict(observed=2,admitted=1,terminal_consumed=True,closed=True)
        assert read_run_budget_state(ledger)['pending_input_tokens']==100
    finally:child.close()
