"""Private completion of an unregistered native tool, never terminal authority."""
from code2paper.agentic.digest import canonical_json_bytes, digest_json
from .protocol import ProtocolError, parse_model
from .writer_contract import ArtifactRefV1


def verify_unknown_tool_rejection(store, task, finish, facts, *, require_settlement=True):
    def refuse():
        raise ProtocolError('backend_release_unknown_tool_unproven')

    keys={'schema_version','execution_id','task_id','task_epoch','request_id','request_digest',
          'session_id','source','finish_reason','raw_ref','session_ref'}
    if (not isinstance(finish,dict) or set(finish)!=keys
            or finish['schema_version']!='DshRejectedUnknownToolProviderQuiescenceV1'
            or finish['source']!='gated-adapter-natural-unknown-tool-exhaustion/1'
            or finish['finish_reason']!='tool-calls' or type(finish['task_epoch']) is not int
            or any(finish[k]!=getattr(store.scope,k) for k in ('execution_id','task_id','task_epoch'))
            or task['captured_source'] is not None or task['receipt'] is not None
            or not task['binding'] or finish['session_id']!=task['binding']['session_id']):refuse()
    def ref(value):return parse_model(canonical_json_bytes(value),ArtifactRefV1)
    raw_ref=ref(finish['raw_ref']);session_ref=ref(finish['session_ref'])
    if (raw_ref.media_type!='application/json' or session_ref.media_type!='application/json'
            or any(getattr(r,k)!=getattr(store.scope,k) for r in (raw_ref,session_ref)
                   for k in ('execution_id','task_id','task_epoch'))):refuse()
    raw=store.read_json(raw_ref);session=store.read_json(session_ref)
    verify_unknown_tool_session(store, raw, session, facts, request_id=finish['request_id'],
        request_digest=finish['request_digest'], session_id=finish['session_id'])
    if not require_settlement:return
    if any(len([f for f in facts if f.kind==k])!=1 for k in ('terminal','settlement')):refuse()
    terminal_fact=next(f for f in facts if f.kind=='terminal');settled=next(f for f in facts if f.kind=='settlement')
    evidence=store.read_json(ref(terminal_fact.evidence_ref))
    if (evidence!={'schema_version':'DshRejectedUnknownToolFinishObservationV1','request_digest':finish['request_digest'],
            'finish_reason':'tool-calls','stream_complete':True,'raw_ref':finish['raw_ref'],'session_ref':finish['session_ref']}
            or terminal_fact.evidence_ref!=settled.evidence_ref):refuse()


def verify_unknown_tool_session(store, raw, session, facts, *, request_id, request_digest, session_id):
    """Check native rejection bytes only; does not mint active completion authority.

    Historical callers must separately prove original producer EOF, scope, grants
    and fees. No artifact, task, reservation or execute observation is written.
    """
    def refuse():
        raise ProtocolError('backend_release_unknown_tool_unproven')
    def ref(value):return parse_model(canonical_json_bytes(value),ArtifactRefV1)
    if (not isinstance(raw,dict) or set(raw)!={'schema_version','tool_call_id','name','arguments'}
            or raw['schema_version']!='DshRejectedUnknownToolCaptureV1'
            or any(not isinstance(raw[k],str) for k in ('tool_call_id','name','arguments'))
            or not raw['tool_call_id'] or not raw['name']
            or not isinstance(session,dict) or set(session)!={'schema_version','session_id','format_version','events'}
            or session['schema_version']!='DshSessionCaptureV1' or session['format_version']!='SessionFileV4'
            or session['session_id']!=session_id or not isinstance(session['events'],list)):refuse()
    events=session['events']
    if (not events or any(not isinstance(e,dict) or type(e.get('seq')) is not int for e in events)
            or any(a['seq']>=b['seq'] for a,b in zip(events,events[1:]))
            or any(e.get('type')=='assistant/attempt' for e in events)):refuse()
    def single(kind):
        rows=[e for e in events if e.get('type')==kind]
        if len(rows)!=1 or not isinstance(rows[0].get('data'),dict):refuse()
        return rows[0]
    event=single('assistant/message');data=event['data'];message=data.get('message')
    if (type(data.get('turn')) is not int or type(data.get('step')) is not int
            or not isinstance(message,dict) or message.get('role')!='assistant'
            or not isinstance(message.get('source'),dict) or message['source'].get('kind')!='model'
            or not isinstance(message.get('content'),list) or not isinstance(data.get('stream'),list)):refuse()
    blocks=message['content'];expected_block={'type':'tool-call','id':raw['tool_call_id'],
        'name':raw['name'],'arguments':raw['arguments']}
    if (any(not isinstance(b,dict) or b.get('type') not in {'text','reasoning','tool-call'} for b in blocks)
            or [b for b in blocks if b['type']=='tool-call']!=[expected_block]):refuse()
    call=single('tool/call');result=single('tool/result');step_end=single('step/end');end=single('turn/end')
    for kind in ('turn/start','step/start','step/end','turn/end','tool/call','tool/result'):
        row=single(kind);d=row['data']
        if (type(d.get('turn')) is not int or d['turn']!=data['turn']
                or (not kind.startswith('turn/') and (type(d.get('step')) is not int or d['step']!=data['step']))):refuse()
        if kind.endswith('start') and row['seq']>=event['seq']:refuse()
    if (not event['seq']<call['seq']<result['seq']<step_end['seq']<end['seq']
            or end['data'].get('reason')!={'kind':'blocked'}
            or any(call['data'].get(k)!=v for k,v in {'callId':raw['tool_call_id'],
                'name':raw['name'],'arguments':raw['arguments']}.items())
            or result.get('sourceEventSeqs')!=[call['seq']]
            or result['data'].get('error')!={'name':'ToolNotFoundError','code':'UNKNOWN_TOOL'}):refuse()
    tool=result['data'].get('message')
    if (not isinstance(tool,dict) or tool.get('role')!='tool' or tool.get('isError') is not True
            or tool.get('toolCallId')!=raw['tool_call_id']
            or tool.get('source')!={'kind':'tool','callId':raw['tool_call_id']}
            or tool.get('content')!=[{'type':'text','text':f'Error: unknown tool "{raw["name"]}"'}]):refuse()
    if (not facts or facts[0].kind!='reserve' or facts[0].invocation_id!=request_id
            or facts[0].request_digest!=request_digest
            or any((f.execution_id,f.task_id,f.task_epoch)!=(store.scope.execution_id,store.scope.task_id,store.scope.task_epoch) for f in facts)
            or any(len([f for f in facts if f.kind==k])!=1 for k in ('reserve','dispatch-recorded','adapter-attempt','usage'))):refuse()
    reserved=store.read_json(ref(facts[0].evidence_ref));actual=store.read_json(ref(reserved['actual_request_ref']))
    tools=actual.get('tools')
    if (digest_json(actual)!=request_digest or not isinstance(tools,list)
            or any(not isinstance(t,dict) or not isinstance(t.get('name'),str) or not t['name'] for t in tools)
            or len({t['name'] for t in tools})!=len(tools) or 'c2p_terminal' not in {t['name'] for t in tools}
            or raw['name'] in {t['name'] for t in tools}
            or any(message['source'].get(k)!=actual.get(k) for k in ('provider','model'))):refuse()
    header=single('request/header');context=single('request/context')
    h=header['data'].get('header',{});c=context['data']
    config={k:actual[k] for k in ('provider','model','maxTokens','temperature','reasoningEffort') if k in actual}
    if (not isinstance(h,dict) or h.get('config')!=config or h.get('tools')!=tools
            or c.get('provider')!=actual.get('provider') or c.get('model')!=actual.get('model')
            or not header['seq']<context['seq']<event['seq']):refuse()
    streams=data['stream'];opened={};closed={};parts={};chunks=[]
    for index,s in enumerate(streams):
        if not isinstance(s,dict):refuse()
        kind=s.get('type')
        if kind in {'text-chunks','reasoning-chunks','tool-call-chunks'}:
            bi=s.get('index');bt={'text-chunks':'text','reasoning-chunks':'reasoning','tool-call-chunks':'tool-call'}[kind]
            values=s.get('args' if bt=='tool-call' else 'texts');dt=s.get('dt')
            if (type(bi) is not int or bi not in opened or bi in closed or opened[bi]!=bt
                    or not isinstance(values,list) or any(not isinstance(v,str) for v in values)
                    or not isinstance(dt,list) or len(dt)!=len(values)-1 or any(type(v) is not int or v<0 for v in dt)
                    or (bt=='tool-call' and (s.get('id')!=raw['tool_call_id'] or s.get('name')!=raw['name']))):refuse()
            parts.setdefault(bi,[]).extend(values)
        elif kind=='chunk' and isinstance(s.get('chunk'),dict):
            chunk=s['chunk'];chunks.append((index,chunk));ck=chunk.get('type')
            if ck=='block-start':
                bi=chunk.get('index');bt=chunk.get('blockType')
                if type(bi) is not int or bi<0 or bi in opened or bt not in {'text','reasoning','tool-call'}:refuse()
                opened[bi]=bt
            elif ck=='block-end':
                bi=chunk.get('index');block=chunk.get('block')
                if type(bi) is not int or bi not in opened or bi in closed or not isinstance(block,dict):refuse()
                if opened[bi]=='tool-call':
                    if block!=expected_block or block['arguments']!=''.join(parts.get(bi,[])):refuse()
                elif block.get('type')!=opened[bi] or block.get('text')!=''.join(parts.get(bi,[])):refuse()
                closed[bi]=block
            elif ck not in {'usage','finish'}:refuse()
        else:refuse()
    usages=[(i,c.get('usage')) for i,c in chunks if c.get('type')=='usage']
    finishes=[(i,c) for i,c in chunks if c.get('type')=='finish']
    if set(opened)!=set(closed) or len(usages)!=1 or len(finishes)!=1:refuse()
    ui,usage=usages[0];fi,terminal=finishes[0]
    if (not isinstance(usage,dict) or any(type(usage.get(k)) is not int or usage[k]<0 for k in ('inputTokens','outputTokens','totalTokens'))
            or usage['totalTokens']!=usage['inputTokens']+usage['outputTokens'] or data.get('usage')!=usage
            or terminal.get('reason')!={'kind':'tool-calls'} or fi!=len(streams)-1 or ui>=fi
            or any(i>=ui for i,c in chunks if c.get('type')=='block-end') or list(closed.values())!=blocks):refuse()
    observed=next(f for f in facts if f.kind=='usage')
    if (usage['inputTokens'],usage['outputTokens'])!=(observed.usage_input_tokens,observed.usage_output_tokens):refuse()
