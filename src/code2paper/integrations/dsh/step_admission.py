"""Explicit V2 Writer-step measurement/admission over the original ledger.

The host observes the real SDK renderer. This module validates that observed
wire; it never constructs a provider request or a second domain TaskView.
Compaction child sends require the separate private auxiliary binding.
"""
from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from code2paper.agentic.authoring_execution_identity import scoped_run_lease
from code2paper.agentic.digest import canonical_json_bytes, digest_json, digest_bytes
from code2paper.agentic.unified_context_models import ConsumerInvocationPlanV1, RunInvocationBudgetEnvelopeV1, DshInvocationEventV1
from code2paper.agentic.unified_invocation_ledger import read_dsh_invocation_events, read_run_budget_state, register_invocation_plan, check_run_budget_before_send, publish_dsh_invocation_event
from .epoch_accounting import epoch_requests, assert_epoch_admission
from .epoch_tools import EpochTools
from .protocol import WireModel, ProtocolError, parse_model, strict_json_loads
from .writer_contract import ArtifactRefV1, WriterTaskContractV2, WriterWireProjectionV1, WriterWireEquivalenceV1, WriterMeasurementV1, Positive, Identifier, Digest


class MeasuredWriterStepV2(WireModel):
    schema_version: Literal['MeasuredWriterStepV2']
    contract_digest: Digest
    sequence: Positive
    role: Literal['writer']
    child_id: Identifier
    session_id: Identifier
    actual_request_ref: ArtifactRefV1
    provider_wire_ref: ArtifactRefV1
    input_tokens: Positive
    output_tokens: Positive
    tokenizer_digest: Digest
    meter_version: Identifier


class LoopInvocationV2(WireModel):
    invocation_id: Identifier
    role: Identifier
    phase: Identifier
    max_input_tokens: Positive
    max_output_tokens: Positive
    page_id: Identifier
    is_repair: bool = False

    @model_validator(mode='after')
    def phase_matches(self):
        if self.role != self.phase:raise ValueError('loop_role_phase_mismatch')
        return self


class LoopPlanV2(WireModel):
    schema_version: Literal['DshLoopPlanV2']
    contract_digest: Digest
    seed_plan_digest: Digest
    envelope_digest: Digest
    profile_digest: Digest
    model_identity_digest: Digest
    plan_revision: Positive
    invocations: tuple[LoopInvocationV2,...]
    reserved_input_tokens_by_role: dict[str,int]
    content_digest: Digest

    @model_validator(mode='after')
    def sealed(self):
        if len({row.invocation_id for row in self.invocations}) != len(self.invocations):
            raise ValueError('loop_invocation_duplicate')
        if self.content_digest != digest_json(self.model_dump(mode='json',exclude={'content_digest'})):
            raise ValueError('loop_plan_digest_mismatch')
        return self


READ_TOOL = {'name':'c2p_read','description':'Read a bounded UTF-8 range from an explicit Kernel-issued grant. Navigation is not evidence. No paths, new grants, scope changes or evidence promotion are accepted.',
    'parameters':{'type':'object','properties':{'grant_id':{'type':'string'},'offset':{'type':'integer'},'length':{'type':'integer'}},
                  'required':['grant_id','offset','length'],'additionalProperties':False}}


def _text(content):
    if not isinstance(content,list) or any(not isinstance(block,dict) or set(block)!={'type','text'} or block['type']!='text' or not isinstance(block['text'],str) for block in content):
        raise ProtocolError('dsh_step_content_unsupported')
    return ''.join(block['text'] for block in content)


def verify_message_wire(messages,wire,*,allow_empty_reasoning=False):
    """Closed text/native-tool history comparison, not a renderer."""
    if not isinstance(messages,list) or not isinstance(wire,list) or len(messages)!=len(wire):
        raise ProtocolError('dsh_step_message_mismatch')
    calls={};answered=set()
    for message,observed in zip(messages,wire):
        if not isinstance(message,dict) or not isinstance(observed,dict):raise ProtocolError('dsh_step_message_mismatch')
        role=message.get('role')
        if (role not in {'system','user','assistant','tool'} or observed.get('role')!=role
                or set(observed)-({'role','content','tool_calls','tool_call_id','name'} | ({'reasoning_content'} if allow_empty_reasoning else set()))):
            raise ProtocolError('dsh_step_message_mismatch')
        if 'reasoning_content' in observed and (role!='assistant' or observed['reasoning_content']!=''):
            raise ProtocolError('dsh_step_message_mismatch')
        if role=='assistant':
            content=message.get('content');text=[];tool_calls=[]
            if not isinstance(content,list):raise ProtocolError('dsh_step_content_unsupported')
            for block in content:
                if not isinstance(block,dict):raise ProtocolError('dsh_step_content_unsupported')
                if block.get('type')=='text':text.append(_text([block]))
                elif block.get('type')=='tool-call' and set(block)=={'type','id','name','arguments'}:
                    if (not isinstance(block['id'],str) or not block['id'] or block['id'] in calls
                            or block['name'] not in {'c2p_read','c2p_terminal'} or not isinstance(block['arguments'],str)):
                        raise ProtocolError('dsh_step_tool_history_invalid')
                    strict_json_loads(block['arguments'].encode())
                    calls[block['id']]=block['name'];tool_calls.append(block)
                else:raise ProtocolError('dsh_step_content_unsupported')
            rendered=observed.get('content')
            if rendered!=''.join(text) and not (not text and rendered is None):raise ProtocolError('dsh_step_message_mismatch')
            actual=observed.get('tool_calls',[])
            if not isinstance(actual,list) or len(actual)!=len(tool_calls):raise ProtocolError('dsh_step_tool_history_invalid')
            for block,call in zip(tool_calls,actual):
                if (not isinstance(call,dict) or set(call)!={'id','type','function'} or call['id']!=block['id'] or call['type']!='function'
                        or not isinstance(call['function'],dict) or set(call['function'])!={'name','arguments'}
                        or call['function']['name']!=block['name'] or not isinstance(call['function']['arguments'],str)
                        or strict_json_loads(call['function']['arguments'].encode())!=strict_json_loads(block['arguments'].encode())):
                    raise ProtocolError('dsh_step_tool_history_invalid')
        else:
            if observed.get('content') not in (_text(message.get('content')),message.get('content')):
                raise ProtocolError('dsh_step_message_mismatch')
            if 'tool_calls' in observed:raise ProtocolError('dsh_step_tool_history_invalid')
            if role=='tool':
                call_id=message.get('toolCallId')
                if (call_id not in calls or call_id in answered or observed.get('tool_call_id')!=call_id
                        or 'name' in observed and observed['name']!=calls[call_id]):
                    raise ProtocolError('dsh_step_tool_history_invalid')
                answered.add(call_id)
            elif 'tool_call_id' in observed or 'name' in observed:raise ProtocolError('dsh_step_tool_history_invalid')
    if set(calls)!=answered:raise ProtocolError('dsh_step_tool_history_incomplete')


class StepAdmission:
    def __init__(self,facade):
        self.facade=facade
        self.root=facade.store.root/'artifacts/06_authoring/invocations'

    def owner(self,contract_ref):
        from .writer_contract import parse_writer_contract
        f=self.facade;f.authorize();f.task_store.authorize(f.claim,require_execute=True);f.verify_composition()
        contract=parse_writer_contract(canonical_json_bytes(f.store.read_json(contract_ref)))
        if not isinstance(contract,WriterTaskContractV2):raise ProtocolError('multistep_contract_required')
        f.check_contract_current(contract)
        view=f.task_store.read()
        if view['prepared']['contract_ref']!=contract_ref.model_dump(mode='json'):raise ProtocolError('dsh_task_contract_ref_mismatch')
        return contract,view

    def validate_wire(self,contract,actual_ref,provider_ref):
        f=self.facade
        projection=parse_model(canonical_json_bytes(f.store.read_json(contract.dsh_wire_contract_ref)),WriterWireProjectionV1)
        equivalent=parse_model(canonical_json_bytes(f.store.read_json(projection.wire_equivalence_ref)),WriterWireEquivalenceV1)
        seed_loop=f.store.read_json(equivalent.loop_request_ref);seed_wire=f.store.read_json(equivalent.provider_wire_ref)
        actual=f.store.read_json(actual_ref);wire=f.store.read_json(provider_ref)
        if (not isinstance(actual,dict) or set(actual)-{'provider','model','reasoningEffort','messages','tools','toolHistory','temperature','maxTokens'}
                or not isinstance(wire,dict)):
            raise ProtocolError('dsh_step_assembly_unsupported')
        for key in ('provider','model','reasoningEffort','temperature'):
            if actual.get(key)!=seed_loop.get(key):raise ProtocolError('dsh_step_options_mismatch')
        if actual.get('maxTokens')!=contract.post_clamp_max_output_tokens:raise ProtocolError('dsh_step_cap_mismatch')
        messages=actual.get('messages')
        if (not isinstance(messages,list) or not messages or any(not isinstance(row,dict) for row in messages)
                or messages[0].get('role')!='system' or _text(messages[0].get('content'))!=projection.system_text
                or any(row.get('role') in {'system','developer'} for row in messages[1:])):
            raise ProtocolError('dsh_step_system_material_mismatch')
        material=canonical_json_bytes(f.store.read_json(contract.writer_request_ref)['input_payload']).decode()
        expected_source={'kind':'code2paper-material','scope':{'executionId':contract.execution_id,'taskId':contract.task_id,
            'sessionId':f.context.session_id,'epoch':contract.task_epoch,'revision':contract.expected_state_revision,'snapshotDigest':f.context.snapshot_digest},
            'materialId':'task-view:'+contract.writer_request_ref.bytes_digest,'materialKind':'writer_task_view','bytesDigest':digest_bytes(material.encode())}
        if not any(row.get('role')=='user' and row.get('source')==expected_source and row.get('content')==[{'type':'text','text':material}] for row in messages):
            raise ProtocolError('material_restoration_required')
        tools=actual.get('tools')
        allowed=[list(projection.tools)]
        if contract.epoch_limits.max_tool_calls:
            # Scoped reads are installed before the native Writer tool. Both
            # registrations must retain their exact schemas and wire order.
            allowed.extend(([*projection.tools,READ_TOOL],[READ_TOOL,*projection.tools]))
        if tools not in allowed:raise ProtocolError('dsh_step_tools_mismatch')
        expected_tools=[{'type':'function','function':{**tool,**({} if contract.effective_options.get('nativeToolSchemaMode')=='server-default' else {'strict':False})}} for tool in tools]
        if wire.get('tools')!=expected_tools:raise ProtocolError('dsh_step_tools_mismatch')
        def options(body):return {key:value for key,value in body.items() if key not in {'messages','tools'}}
        if options(wire)!=options(seed_wire):raise ProtocolError('dsh_step_provider_options_mismatch')
        verify_message_wire(messages,wire.get('messages'),allow_empty_reasoning=
            actual.get('provider')=='deepseek' and actual.get('reasoningEffort')=='off')
        return actual

    def measure(self,*,contract_ref,actual_request_ref,provider_wire_ref,sequence):
        f=self.facade
        with scoped_run_lease(f.store.root,execution_id=f.context.scope.execution_id,blocking=True):
            contract,view=self.owner(contract_ref)
            self.validate_wire(contract,actual_request_ref,provider_wire_ref)
            if f.request_meter is None:raise ProtocolError('request_meter_unavailable')
            tokens=f.request_meter(f.store.read(provider_wire_ref))
            if type(tokens) is not int or tokens<=0:raise ProtocolError('measurement_tokens_mismatch')
            measurement=parse_model(canonical_json_bytes(f.store.read_json(parse_model(canonical_json_bytes(f.store.read_json(contract.dsh_wire_contract_ref)),WriterWireProjectionV1).measurement_ref)),WriterMeasurementV1)
            if tokens+contract.post_clamp_max_output_tokens+measurement.safety_margin_tokens+measurement.thinking_tokens>measurement.context_tokens:
                raise ProtocolError('writer_context_budget_exceeded')
            status=EpochTools(f.task_store,f.store,f.current_state).status(f.claim,contract)
            if status['terminal_consumed'] or status['closed']:raise ProtocolError('dsh_epoch_tool_surface_closed')
            assert_epoch_admission(self.root,contract,epoch_started_ms=view['epoch_started_ms'],input_tokens=tokens,output_tokens=contract.post_clamp_max_output_tokens)
            step=MeasuredWriterStepV2(schema_version='MeasuredWriterStepV2',contract_digest=contract.task_digest,sequence=sequence,
                role='writer',**view['binding'],actual_request_ref=actual_request_ref,provider_wire_ref=provider_wire_ref,
                input_tokens=tokens,output_tokens=contract.post_clamp_max_output_tokens,
                tokenizer_digest=contract.identity.tokenizer_digest,meter_version=f.composition['effective_config']['meter_version'])
            return f.store.put_json(step)

    def measure_auxiliary(self,*,contract_ref,binding_ref,actual_request_ref,provider_wire_ref,sequence):
        from .auxiliary_admission import AuxiliaryAdmission, MeasuredCompactionStepV2
        f=self.facade
        with scoped_run_lease(f.store.root,execution_id=f.context.scope.execution_id,blocking=True):
            contract,view=self.owner(contract_ref)
            binding=AuxiliaryAdmission(f).binding(binding_ref,contract,execute=True)
            if f.request_meter is None:raise ProtocolError('request_meter_unavailable')
            tokens=f.request_meter(f.store.read(provider_wire_ref))
            if type(tokens) is not int or tokens<=0:raise ProtocolError('measurement_tokens_mismatch')
            step=MeasuredCompactionStepV2(schema_version='MeasuredCompactionStepV2',contract_digest=contract.task_digest,
                sequence=sequence,role='compaction',child_id=binding.child_id,session_id=binding.session_id,
                actual_request_ref=actual_request_ref,provider_wire_ref=provider_wire_ref,input_tokens=tokens,
                output_tokens=binding.output_tokens,tokenizer_digest=contract.identity.tokenizer_digest,
                meter_version=f.composition['effective_config']['meter_version'],binding_ref=binding_ref)
            AuxiliaryAdmission(f).validate_wire(contract,step)
            projection=parse_model(canonical_json_bytes(f.store.read_json(contract.dsh_wire_contract_ref)),WriterWireProjectionV1)
            m=parse_model(canonical_json_bytes(f.store.read_json(projection.measurement_ref)),WriterMeasurementV1)
            if tokens+step.output_tokens+m.safety_margin_tokens+m.thinking_tokens>m.context_tokens:
                raise ProtocolError('writer_context_budget_exceeded')
            status=EpochTools(f.task_store,f.store,f.current_state).status(f.claim,contract)
            if status['terminal_consumed'] or status['closed']:raise ProtocolError('dsh_epoch_tool_surface_closed')
            assert_epoch_admission(self.root,contract,epoch_started_ms=view['epoch_started_ms'],input_tokens=tokens,output_tokens=step.output_tokens)
            return f.store.put_json(step)

    def reserve(self,*,contract_ref,budget_ref,step_ref,event_id):
        f=self.facade
        with scoped_run_lease(f.store.root,execution_id=f.context.scope.execution_id,blocking=True):
            contract,view=self.owner(contract_ref)
            from .auxiliary_admission import parse_step, AuxiliaryAdmission
            step=parse_step(f.store.read_json(step_ref))
            auxiliary=step.role=='compaction'
            binding=AuxiliaryAdmission(f).binding(step.binding_ref,contract,execute=True) if auxiliary else None
            if (step.contract_digest!=contract.task_digest or {'child_id':step.child_id,'session_id':step.session_id}!=({'child_id':binding.child_id,'session_id':binding.session_id} if auxiliary else view['binding'])
                    or step.tokenizer_digest!=contract.identity.tokenizer_digest
                    or step.output_tokens!=(binding.output_tokens if auxiliary else contract.post_clamp_max_output_tokens)
                    or step.meter_version!=f.composition['effective_config']['meter_version']):raise ProtocolError('dsh_step_binding_mismatch')
            seed=ConsumerInvocationPlanV1.model_validate_json(canonical_json_bytes(f.store.read_json(contract.plan_ref)))
            envelope=RunInvocationBudgetEnvelopeV1.model_validate_json(canonical_json_bytes(f.store.read_json(budget_ref)))
            if (envelope.content_digest!=seed.envelope_digest or envelope.profile_digest!=contract.identity.profile_digest
                    or envelope.model_identity_digest!=contract.identity.model_digest):raise ProtocolError('dsh_budget_envelope_binding_mismatch')
            # Revalidate original owner dependencies and the fresh dynamic wire,
            # never reuse the seed measurement for later messages or tool results.
            f.verify_contract_dependencies(contract)
            AuxiliaryAdmission(f).validate_wire(contract,step) if auxiliary else self.validate_wire(contract,step.actual_request_ref,step.provider_wire_ref)
            tokens=f.request_meter(f.store.read(step.provider_wire_ref))
            if tokens!=step.input_tokens:raise ProtocolError('measurement_tokens_mismatch')
            requests=epoch_requests(self.root,contract)
            if step.sequence!=len(requests)+1:raise ProtocolError('dsh_step_sequence_mismatch')
            status=EpochTools(f.task_store,f.store,f.current_state).status(f.claim,contract)
            if status['terminal_consumed'] or status['closed']:raise ProtocolError('dsh_epoch_tool_surface_closed')
            assert_epoch_admission(self.root,contract,epoch_started_ms=view['epoch_started_ms'],input_tokens=tokens,output_tokens=step.output_tokens)
            if read_run_budget_state(self.root)['pending_call_count']:raise ProtocolError('dsh_run_has_unsettled_request')
            section=f.store.read_json(contract.private_input_ref);page=section['prompt_payload']['unified_v2_page_id']
            primary=[row for row in seed.invocations if row.role=='writer' and not row.is_repair and row.page_id==page]
            if len(primary)!=1:raise ProtocolError('dsh_invocation_plan_scope_invalid')
            invocation_id=primary[0].invocation_id if step.role=='writer' and not any(facts[0].consumer_role=='writer' for facts in requests) else step.role+'-step:'+digest_json({'task_digest':contract.task_digest,'sequence':step.sequence}).split(':')[1]
            if (step.role not in envelope.request_budget_by_role or tokens>envelope.max_request_input_tokens_by_role[step.role]
                    or step.output_tokens>envelope.request_budget_by_role[step.role].output_token_reserve):
                raise ProtocolError('dsh_step_role_cap_exceeded')
            plan=self.plan(contract,seed,envelope,invocation_id,page,tokens,step.output_tokens,role=step.role)
            register_invocation_plan(self.root,plan)
            failures=check_run_budget_before_send(self.root,envelope,role=step.role,request_input_tokens=tokens,
                current_attempt_recorded=False,invocation_id=invocation_id)
            if failures:raise ProtocolError(failures[0])
            evidence=f.store.put_json({'schema_version':'DshReserveEvidenceV2','budget_ref':budget_ref,'step_ref':step_ref,
                'actual_request_ref':step.actual_request_ref,'loop_plan_ref':f.store.put_json(plan)})
            event=DshInvocationEventV1(event_id=event_id,kind='reserve',invocation_id=invocation_id,attempt=1,
                execution_id=contract.execution_id,task_id=contract.task_id,task_epoch=contract.task_epoch,
                claim_digest=digest_json(f.claim),request_digest=digest_json(f.store.read_json(step.actual_request_ref)),
                contract_digest=contract.task_digest,plan_digest=plan.content_digest,consumer_role=step.role,source='kernel',
                reserved_input_tokens=tokens,reserved_output_tokens=step.output_tokens,evidence_ref=evidence.model_dump(mode='json'))
            publish_dsh_invocation_event(self.root,event)
            if read_dsh_invocation_events(self.root,invocation_id)!=(event,):raise ProtocolError('dsh_reserve_readback_failed')
            from .invocation_adapter import InvocationAdapter
            return InvocationAdapter._reservation(event)

    def plan(self,contract,seed,envelope,invocation_id,page,tokens,output,*,role='writer'):
        # Preserve all current role plans/future pages, including plans issued
        # by other task owners. A new step cannot discard their reservations.
        records=[strict_json_loads(path.read_bytes()) for path in sorted((self.root/'plans').glob('*.json'))]
        revision=max([seed.plan_revision,*[row['plan_revision'] for row in records]])+1
        entries={row.invocation_id:LoopInvocationV2(invocation_id=row.invocation_id,role=row.role,phase=row.phase,
            max_input_tokens=row.max_input_tokens,max_output_tokens=row.max_output_tokens,page_id=row.page_id,is_repair=row.is_repair) for row in seed.invocations}
        for existing_role in {entry['role'] for row in records for entry in row['invocations'].values()}:
            latest=max((row for row in records if any(entry['role']==existing_role for entry in row['invocations'].values())),key=lambda row:row['plan_revision'])
            for key,entry in latest['invocations'].items():
                if entry['role']==existing_role:
                    entries[key]=LoopInvocationV2(invocation_id=key,role=entry['role'],phase=entry['phase'],
                        max_input_tokens=entry['max_input_tokens'],max_output_tokens=entries[key].max_output_tokens if key in entries
                            else envelope.request_budget_by_role[existing_role].output_token_reserve,page_id=entry['page_id'],is_repair=entry['is_repair'])
        if invocation_id not in entries:
            entries[invocation_id]=LoopInvocationV2(invocation_id=invocation_id,role=role,phase=role,
                max_input_tokens=tokens,max_output_tokens=output,page_id=page)
        elif tokens>entries[invocation_id].max_input_tokens:raise ProtocolError('dsh_step_planned_input_exceeded')
        values=dict(schema_version='DshLoopPlanV2',contract_digest=contract.task_digest,seed_plan_digest=seed.content_digest,
            envelope_digest=envelope.content_digest,profile_digest=envelope.profile_digest,model_identity_digest=envelope.model_identity_digest,
            plan_revision=revision,invocations=tuple(entries[key] for key in sorted(entries)),
            reserved_input_tokens_by_role=dict(seed.reserved_input_tokens_by_role))
        return LoopPlanV2(**values,content_digest=digest_json(values))
