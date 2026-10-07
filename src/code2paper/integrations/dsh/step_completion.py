"""Host-private V2 per-step completion; no domain acceptance or owner release.

The original fee journal is closed only after the actual SDK step ended and
its immutable Session proves one naturally exhausted stream and observed usage.
A turn may remain running: this proof grants only the next bounded step.
"""
from code2paper.agentic.digest import canonical_json_bytes, digest_json
from .protocol import ProtocolError, parse_model, strict_json_loads
from .writer_contract import ArtifactRefV1


def verify_step_completion(facade, contract, evidence, facts):
    def refuse():
        raise ProtocolError('dsh_step_completion_unproven')

    keys={'schema_version','request_id','request_digest','session_id','turn_id','step_id',
          'source','finish_reason','stream_complete','session_ref'}
    if (contract.schema_version!='WriterTaskContractV2' or not isinstance(evidence,dict)
            or set(evidence)!=keys or evidence['schema_version']!='DshStepFinishObservationV2'
            or evidence['source']!='gated-adapter-natural-exhaustion/2' or evidence['stream_complete'] is not True
            or evidence['finish_reason'] not in {'stop','tool-calls'}
            or any(type(evidence[k]) is not int or evidence[k]<1 for k in ('turn_id','step_id'))):refuse()
    if (not facts or facts[0].kind!='reserve' or facts[0].contract_digest!=contract.task_digest
            or facts[0].invocation_id!=evidence['request_id'] or facts[0].request_digest!=evidence['request_digest']
            or any((f.execution_id,f.task_id,f.task_epoch)!=(contract.execution_id,contract.task_id,contract.task_epoch) for f in facts)
            or any(len([f for f in facts if f.kind==k])!=1 for k in ('reserve','dispatch-recorded','adapter-attempt','usage'))):refuse()
    store=facade.store
    def read(ref):return store.read_json(parse_model(canonical_json_bytes(ref),ArtifactRefV1))
    reserve=read(facts[0].evidence_ref)
    if reserve.get('schema_version')!='DshReserveEvidenceV2':refuse()
    from .auxiliary_admission import parse_step, AuxiliaryAdmission
    step=parse_step(read(reserve['step_ref']))
    auxiliary=step.role=='compaction'
    binding=AuxiliaryAdmission(facade).binding(step.binding_ref,contract,recorded_claim_digest=facts[0].claim_digest) if auxiliary else None
    actual=read(step.actual_request_ref.model_dump(mode='json'))
    if any(not isinstance(actual.get(k),str) or not actual[k] for k in ('provider','model')):refuse()
    view=facade.task_store.read()
    if (({'child_id':binding.child_id,'session_id':binding.session_id} if auxiliary else view['binding'])!={'child_id':step.child_id,'session_id':step.session_id}
            or step.session_id!=evidence['session_id'] or step.contract_digest!=contract.task_digest
            or digest_json(actual)!=evidence['request_digest']):refuse()
    session=read(evidence['session_ref'])
    if (not isinstance(session,dict) or set(session)!={'schema_version','session_id','format_version','events'}
            or session['schema_version']!='DshSessionCaptureV1' or session['format_version']!='SessionFileV4'
            or session['session_id']!=step.session_id or not isinstance(session['events'],list)):refuse()
    events=session['events']
    if (not events or any(not isinstance(e,dict) or type(e.get('seq')) is not int for e in events)
            or any(a['seq']>=b['seq'] for a,b in zip(events,events[1:]))):refuse()
    def bound(kind):
        return [e for e in events if e.get('type')==kind and isinstance(e.get('data'),dict)
                and e['data'].get('turn')==evidence['turn_id'] and e['data'].get('step')==evidence['step_id']]
    messages=bound('assistant/message');starts=bound('step/start');ends=bound('step/end')
    if len(messages)!=1 or len(starts)!=1 or len(ends)!=1:refuse()
    start,event,end=starts[0],messages[0],ends[0]
    if not start['seq']<event['seq']<end['seq']:refuse()
    # DSH logs header/context changes, not one duplicate per request. Bind
    # the request ordinal to completed assistant events and inherit only the
    # latest actual header/context, checked against this step's measured wire.
    from .epoch_accounting import epoch_requests
    ordinal=0
    for prior in epoch_requests(store.root/'artifacts/06_authoring/invocations',contract):
        r=read(prior[0].evidence_ref);s=parse_step(read(r['step_ref']))
        if s.session_id==step.session_id and s.sequence<=step.sequence:ordinal+=1
    if len([e for e in events if e.get('type')=='assistant/message' and e['seq']<end['seq']])!=ordinal:refuse()
    window=[e for e in events if start['seq']<e['seq']<event['seq']]
    if any(e.get('type')=='assistant/attempt' for e in window):refuse()
    headers=[e for e in events if e.get('type')=='request/header' and e['seq']<event['seq']][-1:]
    contexts=[e for e in events if e.get('type')=='request/context' and e['seq']<event['seq']][-1:]
    if len(headers)!=1 or len(contexts)!=1 or headers[0]['seq']>=event['seq'] or contexts[0]['seq']>=event['seq']:refuse()
    config={k:actual[k] for k in ('provider','model','maxTokens','temperature','reasoningEffort') if k in actual}
    header=headers[0].get('data',{}).get('header',{});context=contexts[0].get('data',{})
    data=event['data'];message=data.get('message',{});source=message.get('source',{})
    if (header.get('config')!=config or header.get('tools')!=actual.get('tools')
            or any(context.get(k)!=actual.get(k) or source.get(k)!=actual.get(k) for k in ('provider','model'))
            or message.get('role')!='assistant' or source.get('kind')!='model'
            or not isinstance(data.get('stream'),list)):refuse()
    streams=data['stream'];opened={};closed={};parts={};calls={};usage=None;finish=None;ui=None
    for i,s in enumerate(streams):
        if not isinstance(s,dict):refuse()
        kind=s.get('type');bi=s.get('index')
        if kind in {'text-chunks','reasoning-chunks','tool-call-chunks'}:
            field='args' if kind=='tool-call-chunks' else 'texts'
            typ={'text-chunks':'text','reasoning-chunks':'reasoning','tool-call-chunks':'tool-call'}[kind]
            values=s.get(field);dt=s.get('dt')
            if (type(bi) is not int or opened.get(bi)!=typ or bi in closed or usage is not None
                    or not isinstance(values,list) or not values or any(not isinstance(v,str) for v in values)
                    or not isinstance(dt,list) or len(dt)!=len(values)-1
                    or any(type(v) is not int or v<0 for v in dt)):refuse()
            parts.setdefault(bi,[]).extend(values)
            if typ=='tool-call':
                call=calls.setdefault(bi,{})
                for key in ('id','name'):
                    if key in s:
                        if not isinstance(s[key],str) or not s[key] or key in call and call[key]!=s[key]:refuse()
                        call[key]=s[key]
        elif kind=='chunk' and isinstance(s.get('chunk'),dict):
            c=s['chunk'];ck=c.get('type');bi=c.get('index')
            if ck=='block-start':
                typ=c.get('blockType')
                if type(bi) is not int or bi<0 or bi in opened or typ not in {'text','reasoning','tool-call'} or usage is not None:refuse()
                opened[bi]=typ
            elif ck=='block-end':
                block=c.get('block')
                if (type(bi) is not int or bi not in opened or bi in closed or usage is not None
                        or not isinstance(block,dict) or block.get('type')!=opened[bi]):refuse()
                text=''.join(parts.get(bi,[]))
                if opened[bi]=='tool-call':
                    call=calls.get(bi,{})
                    if set(call)!={'id','name'} or any(block.get(k)!=call[k] for k in call):refuse()
                    args=block.get('arguments')
                    if not isinstance(args,str):refuse()
                    if args!=text:
                        if digest_json(strict_json_loads(args))!=digest_json(strict_json_loads(text)):refuse()
                elif block.get('text')!=text:refuse()
                closed[bi]=block
            elif ck=='usage':
                if usage is not None or set(opened)!=set(closed):refuse()
                usage=c.get('usage');ui=i
            elif ck=='finish':
                if finish is not None or usage is None or i!=len(streams)-1:refuse()
                finish=c.get('reason')
            else:refuse()
        else:refuse()
    if (set(opened)!=set(closed) or not isinstance(usage,dict) or ui is None or finish!={'kind':evidence['finish_reason']}
            or any(type(usage.get(k)) is not int or usage[k]<0 for k in ('inputTokens','outputTokens','totalTokens'))
            or usage['totalTokens']!=usage['inputTokens']+usage['outputTokens'] or data.get('usage')!=usage
            or list(closed.values())!=message.get('content')):refuse()
    observed=next(f for f in facts if f.kind=='usage')
    if (usage['inputTokens'],usage['outputTokens'])!=(observed.usage_input_tokens,observed.usage_output_tokens):refuse()
    if bool(calls)!=(evidence['finish_reason']=='tool-calls'):refuse()
    if auxiliary and (calls or evidence['finish_reason']!='stop' or any(b.get('type')!='text' for b in closed.values())
            or not any(b.get('text','').strip() for b in closed.values())):refuse()
    # Every native tool block must have the original pre-schema observer receipt.
    from .epoch_tools import EpochTools
    tools=EpochTools(facade.task_store,store,facade.current_state)
    with facade.task_store._transaction() as db:
        rows=[r['source'] for r in tools._rows(db,contract) if r['source']['request_id']==facts[0].invocation_id]
    if len(rows)!=len(calls):refuse()
    ids=set()
    for bi,call in calls.items():
        if call['id'] in ids:refuse()
        ids.add(call['id'])
        matches=[r for r in rows if r['tool_call_id']==call['id'] and r['name']==call['name'] and r['session_id']==step.session_id]
        if len(matches)!=1:refuse()
        raw=store.read(parse_model(canonical_json_bytes(matches[0]['arguments_ref']),ArtifactRefV1))
        if raw!=''.join(parts[bi]).encode('utf-8'):refuse()
        tool_calls=[e for e in bound('tool/call') if e['data'].get('callId')==call['id']]
        results=[e for e in bound('tool/result') if e['data'].get('message',{}).get('toolCallId')==call['id']]
        if (len(tool_calls)!=1 or len(results)!=1 or not event['seq']<tool_calls[0]['seq']<results[0]['seq']<end['seq']
                or tool_calls[0]['data'].get('name')!=call['name']
                or tool_calls[0]['data'].get('arguments')!=closed[bi]['arguments']
                or results[0].get('sourceEventSeqs')!=[tool_calls[0]['seq']]
                or results[0]['data']['message'].get('role')!='tool'
                or results[0]['data']['message'].get('source')!={'kind':'tool','callId':call['id']}
                or type(results[0]['data']['message'].get('isError',False)) is not bool):refuse()
    if len(bound('tool/call'))!=len(calls) or len(bound('tool/result'))!=len(calls):refuse()
