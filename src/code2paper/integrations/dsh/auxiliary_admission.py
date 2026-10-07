"""Host-issued, separately bound compaction input; no new financial ledger.

Only the private Worker can issue these bindings. Derived summaries never
become Writer evidence. An undeclared auxiliary role cannot acquire a send.
"""
from typing import Literal
from code2paper.agentic.digest import canonical_json_bytes, digest_json
from code2paper.agentic.authoring_execution_identity import scoped_run_lease
from code2paper.agentic.unified_context_models import ConsumerInvocationPlanV1, RunInvocationBudgetEnvelopeV1
from .protocol import WireModel, ProtocolError, parse_model, strict_json_loads
from .writer_contract import ArtifactRefV1, Identifier, Digest, Positive, WriterWireProjectionV1, WriterWireEquivalenceV1
from .step_admission import MeasuredWriterStepV2, _text, verify_message_wire

COMPACTION_SYSTEM = ('You are a context compaction agent. Produce navigation summaries only. '
    'A summary does not authorize source evidence, factual claims, formulas, or final publication prose. '
    'Return plain text and never call tools.')

COMPACTION_INSTRUCTION = ('Summarize the supplied conversation for navigation only. Preserve open tasks, '
    'decisions and unresolved questions. Return plain text. This derived summary is not source evidence '
    'and does not authorize factual claims, source spans, formulas, or final prose. Do not call tools.')


class CompactionBindingV2(WireModel):
    schema_version: Literal['DshCompactionBindingV2']
    contract_digest: Digest
    claim_digest: Digest
    parent_session_id: Identifier
    child_id: Identifier
    session_id: Identifier
    transaction_id: Identifier
    parent_session_ref: ArtifactRefV1
    input_ref: ArtifactRefV1
    prompt_text: str
    output_tokens: Positive


class MeasuredCompactionStepV2(MeasuredWriterStepV2):
    schema_version: Literal['MeasuredCompactionStepV2']
    role: Literal['compaction']
    binding_ref: ArtifactRefV1


def parse_step(value):
    cls=MeasuredCompactionStepV2 if value.get('schema_version')=='MeasuredCompactionStepV2' else MeasuredWriterStepV2
    return parse_model(canonical_json_bytes(value),cls)


class AuxiliaryAdmission:
    def __init__(self,facade):self.f=facade

    def binding(self,ref,contract,*,execute=False,recorded_claim_digest=None):
        f=self.f;value=parse_model(canonical_json_bytes(f.store.read_json(ref)),CompactionBindingV2)
        view=f.task_store.read()
        if (value.contract_digest!=contract.task_digest or not view['binding']
                or value.parent_session_id!=view['binding']['session_id'] or value.session_id==value.parent_session_id
                or (value.claim_digest!=recorded_claim_digest if recorded_claim_digest is not None
                    else not f.task_store.accepts_recorded_claim(f.claim,value.claim_digest))):
            raise ProtocolError('dsh_aux_binding_mismatch')
        if execute and value.claim_digest!=digest_json(f.claim):raise ProtocolError('dsh_aux_claim_stale')
        with f.task_store._transaction() as db:
            if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='auxiliary_bindings'").fetchone() is None:
                raise ProtocolError('dsh_aux_binding_unissued')
            row=db.execute('SELECT binding FROM auxiliary_bindings WHERE task_key=? AND transaction_id=?',
                (f.task_store.key,value.transaction_id)).fetchone()
            if row is None or bytes(row['binding'])!=canonical_json_bytes(value):raise ProtocolError('dsh_aux_binding_unissued')
        return value

    def issue(self,*,contract_ref,budget_ref,parent_session_ref,input_ref,child_id,session_id,output_tokens):
        from .step_admission import StepAdmission
        f=self.f
        with scoped_run_lease(f.store.root,execution_id=f.context.scope.execution_id,blocking=True):
            contract,view=StepAdmission(f).owner(contract_ref);f.verify_contract_dependencies(contract)
            seed=ConsumerInvocationPlanV1.model_validate_json(canonical_json_bytes(f.store.read_json(contract.plan_ref)))
            budget=RunInvocationBudgetEnvelopeV1.model_validate_json(canonical_json_bytes(f.store.read_json(budget_ref)))
            role=budget.request_budget_by_role.get('compaction')
            if (budget.content_digest!=seed.envelope_digest or role is None or budget.max_calls_by_role.get('compaction',0)<1
                    or output_tokens>role.output_token_reserve):raise ProtocolError('dsh_aux_role_undeclared')
            if not view['binding'] or child_id!=session_id or session_id==view['binding']['session_id']:
                raise ProtocolError('dsh_aux_binding_mismatch')
            parent=f.store.read_json(parent_session_ref);inp=f.store.read_json(input_ref)
            if (not isinstance(parent,dict) or set(parent)!={'schema_version','session_id','format_version','events'}
                    or parent['schema_version']!='DshSessionCaptureV1' or parent['format_version']!='SessionFileV4'
                    or parent['session_id']!=view['binding']['session_id'] or not isinstance(parent['events'],list)
                    or not isinstance(inp,dict) or set(inp)-{'messages','tools'} or not isinstance(inp.get('messages'),list)
                    or not inp['messages']):raise ProtocolError('dsh_aux_input_invalid')
            events=parent['events']
            if (any(not isinstance(e,dict) or type(e.get('seq')) is not int for e in events)
                    or any(a['seq']>=b['seq'] for a,b in zip(events,events[1:]))):raise ProtocolError('dsh_aux_input_invalid')
            starts=[e for e in events if e.get('type')=='compaction/start']
            if not starts:raise ProtocolError('compaction_transaction_required')
            start=starts[-1];transaction=start.get('data',{}).get('compactionId')
            if (not isinstance(transaction,str) or not transaction or any(e.get('type')=='compaction/end'
                    and e.get('data',{}).get('compactionId')==transaction for e in events if e['seq']>start['seq'])):
                raise ProtocolError('compaction_transaction_required')
            prompt=COMPACTION_INSTRUCTION+'\n'+canonical_json_bytes(inp).decode()
            value=CompactionBindingV2(schema_version='DshCompactionBindingV2',contract_digest=contract.task_digest,
                claim_digest=digest_json(f.claim),parent_session_id=parent['session_id'],child_id=child_id,session_id=session_id,
                transaction_id=transaction,parent_session_ref=parent_session_ref,input_ref=input_ref,prompt_text=prompt,output_tokens=output_tokens)
            ref=f.store.put_json(value)
            with f.task_store._transaction() as db:
                # Metadata only. Every cost remains in original invocation facts.
                db.execute('CREATE TABLE IF NOT EXISTS auxiliary_bindings (task_key TEXT NOT NULL, transaction_id TEXT NOT NULL, binding BLOB NOT NULL, PRIMARY KEY(task_key,transaction_id))')
                old=db.execute('SELECT binding FROM auxiliary_bindings WHERE task_key=? AND transaction_id=?',(f.task_store.key,transaction)).fetchone()
                if old is not None and bytes(old['binding'])!=canonical_json_bytes(value):raise ProtocolError('dsh_aux_transaction_already_bound')
                db.execute('INSERT OR IGNORE INTO auxiliary_bindings VALUES (?,?,?)',(f.task_store.key,transaction,canonical_json_bytes(value)))
            return ref,value

    def validate_wire(self,contract,step):
        f=self.f;b=self.binding(step.binding_ref,contract,execute=True)
        if (step.child_id,step.session_id,step.output_tokens)!=(b.child_id,b.session_id,b.output_tokens):
            raise ProtocolError('dsh_aux_binding_mismatch')
        projection=parse_model(canonical_json_bytes(f.store.read_json(contract.dsh_wire_contract_ref)),WriterWireProjectionV1)
        equivalent=parse_model(canonical_json_bytes(f.store.read_json(projection.wire_equivalence_ref)),WriterWireEquivalenceV1)
        seed=f.store.read_json(equivalent.loop_request_ref);seed_wire=f.store.read_json(equivalent.provider_wire_ref)
        actual=f.store.read_json(step.actual_request_ref);wire=f.store.read_json(step.provider_wire_ref)
        if (not isinstance(actual,dict) or set(actual)-{'provider','model','reasoningEffort','messages','tools','toolHistory','temperature','maxTokens'}
                or any(actual.get(k)!=seed.get(k) for k in ('provider','model','reasoningEffort','temperature'))
                or actual.get('maxTokens')!=b.output_tokens or actual.get('tools') not in (None,[]) or actual.get('toolHistory') not in (None,{'tools':[],'updates':[]})):
            raise ProtocolError('dsh_aux_assembly_mismatch')
        messages=actual.get('messages')
        if (not isinstance(messages,list) or len(messages)!=2 or messages[0].get('role')!='system'
                or _text(messages[0].get('content'))!=COMPACTION_SYSTEM or messages[1].get('role')!='user'
                or _text(messages[1].get('content'))!=b.prompt_text):raise ProtocolError('dsh_aux_input_mismatch')
        def options(body):return {k:v for k,v in body.items() if k not in {'messages','tools','tool_choice'}}
        expected=options(seed_wire);expected['max_tokens']=b.output_tokens
        if (not isinstance(wire,dict) or options(wire)!=expected or wire.get('tools') not in (None,[])
                or wire.get('tool_choice') not in (None,'none')):raise ProtocolError('dsh_aux_provider_options_mismatch')
        verify_message_wire(messages,wire.get('messages'),allow_empty_reasoning=actual.get('provider')=='deepseek' and actual.get('reasoningEffort')=='off')
        return b
