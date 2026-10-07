"""Private natural text-stop proof; never a Writer terminal or domain candidate."""
from __future__ import annotations

from code2paper.agentic.digest import canonical_json_bytes, digest_json
from .protocol import ProtocolError, parse_model
from .writer_contract import ArtifactRefV1


def verify_text_rejection(store, task, finish, facts, *, require_settlement=True):
    def refuse():
        raise ProtocolError('backend_release_text_stop_unproven')

    keys={'schema_version','execution_id','task_id','task_epoch','request_id','request_digest',
          'session_id','source','finish_reason','raw_ref','session_ref'}
    if (not isinstance(finish,dict) or set(finish) != keys
            or finish['schema_version'] != 'DshRejectedTextProviderQuiescenceV1'
            or finish['source'] != 'gated-adapter-natural-text-exhaustion/1'
            or finish['finish_reason'] != 'stop' or type(finish['task_epoch']) is not int
            or any(finish[k] != getattr(store.scope,k) for k in ('execution_id','task_id','task_epoch'))
            or task['captured_source'] is not None or task['receipt'] is not None
            or not task['binding'] or finish['session_id'] != task['binding']['session_id']):
        refuse()
    def read(value):
        return parse_model(canonical_json_bytes(value),ArtifactRefV1)
    raw_ref=read(finish['raw_ref']);session_ref=read(finish['session_ref'])
    if raw_ref.media_type != 'text/plain' or session_ref.media_type != 'application/json':refuse()
    raw=store.read(raw_ref);session=store.read_json(session_ref)
    if (not isinstance(session,dict) or set(session) != {'schema_version','session_id','format_version','events'}
            or session['schema_version'] != 'DshSessionCaptureV1' or session['format_version'] != 'SessionFileV4'
            or session['session_id'] != finish['session_id'] or not isinstance(session['events'],list)):
        refuse()
    events=session['events']
    if (not events or any(not isinstance(e,dict) or type(e.get('seq')) is not int for e in events)
            or any(a['seq'] >= b['seq'] for a,b in zip(events,events[1:]))
            or any(e.get('type') in {'assistant/attempt','tool/call','tool/result'} for e in events)):
        refuse()
    messages=[e for e in events if e.get('type')=='assistant/message']
    if len(messages) != 1:refuse()
    event=messages[0];data=event.get('data')
    if (not isinstance(data,dict) or type(data.get('turn')) is not int or type(data.get('step')) is not int
            or not isinstance(data.get('message'),dict) or not isinstance(data.get('stream'),list)):
        refuse()
    message=data['message'];blocks=message.get('content')
    if (message.get('role') != 'assistant' or not isinstance(message.get('source'),dict) or message['source'].get('kind') != 'model'
            or not isinstance(blocks,list) or any(not isinstance(b,dict) or b.get('type') not in {'text','reasoning'} for b in blocks)):
        refuse()
    texts=[b for b in blocks if b['type']=='text']
    if (not texts or any(not isinstance(b.get('text'),str) for b in texts)
            or ''.join(b['text'] for b in texts).encode('utf-8') != raw):refuse()
    for kind in ('turn/start','step/start','step/end','turn/end'):
        bound=[e for e in events if e.get('type')==kind and isinstance(e.get('data'),dict)
            and e['data'].get('turn')==data['turn']
            and (kind.startswith('turn/') or e['data'].get('step')==data['step'])]
        if len(bound) != 1:refuse()
        if kind.endswith('start') and bound[0]['seq'] >= event['seq']:refuse()
        if kind=='step/end':step_end=bound[0]
        if kind=='turn/end':end=bound[0]
    if (not event['seq'] < step_end['seq'] < end['seq']
            or end['data'].get('reason') != {'kind':'completed'}):refuse()
    if (not facts or facts[0].kind != 'reserve' or facts[0].invocation_id != finish['request_id']
            or facts[0].request_digest != finish['request_digest']
            or any((f.execution_id,f.task_id,f.task_epoch) !=
                (finish['execution_id'],finish['task_id'],finish['task_epoch']) for f in facts)
            or any(len([f for f in facts if f.kind==k]) != 1 for k in ('reserve','dispatch-recorded','adapter-attempt','usage'))):
        refuse()
    reserve=store.read_json(read(facts[0].evidence_ref));actual_ref=read(reserve['actual_request_ref'])
    actual=store.read_json(actual_ref)
    if (digest_json(actual) != finish['request_digest']
            or any(message['source'].get(k) != actual.get(k) for k in ('provider','model'))):refuse()
    headers=[e for e in events if e.get('type')=='request/header']
    contexts=[e for e in events if e.get('type')=='request/context']
    if len(headers) != 1 or len(contexts) != 1:refuse()
    header=headers[0].get('data',{}).get('header',{});context=contexts[0].get('data',{})
    expected_config={k:actual[k] for k in ('provider','model','maxTokens','temperature','reasoningEffort') if k in actual}
    if (header.get('config') != expected_config or header.get('tools') != actual.get('tools')
            or context.get('provider') != actual.get('provider') or context.get('model') != actual.get('model')
            or not headers[0]['seq'] < contexts[0]['seq'] < event['seq']):refuse()
    streams=data['stream'];chunks=[];opened={};closed={};parts={}
    if any(not isinstance(s,dict) for s in streams):refuse()
    for index,s in enumerate(streams):
        kind=s.get('type')
        if kind in {'text-chunks','reasoning-chunks'}:
            bi=s.get('index');values=s.get('texts');dt=s.get('dt')
            if (type(bi) is not int or bi not in opened or bi in closed
                    or opened[bi] != ('text' if kind=='text-chunks' else 'reasoning')
                    or not isinstance(values,list) or any(not isinstance(v,str) for v in values)
                    or not isinstance(dt,list) or len(dt) != len(values)-1
                    or any(type(v) is not int or v<0 for v in dt)):
                refuse()
            parts.setdefault(bi,[]).extend(values)
        elif kind=='chunk' and isinstance(s.get('chunk'),dict):
            chunk=s['chunk'];chunks.append((index,chunk));ck=chunk.get('type')
            if ck=='block-start':
                bi=chunk.get('index');bt=chunk.get('blockType')
                if type(bi) is not int or bi<0 or bi in opened or bt not in {'text','reasoning'}:refuse()
                opened[bi]=bt
            elif ck=='block-end':
                bi=chunk.get('index');block=chunk.get('block')
                if (type(bi) is not int or bi not in opened or bi in closed or not isinstance(block,dict)
                        or block.get('type') != opened[bi] or block.get('text') != ''.join(parts.get(bi,[]))):refuse()
                closed[bi]=block
            elif ck not in {'usage','finish'}:refuse()
        else:refuse()
    usages=[(i,c.get('usage')) for i,c in chunks if c.get('type')=='usage']
    finishes=[(i,c) for i,c in chunks if c.get('type')=='finish']
    if set(opened) != set(closed) or len(usages)!=1 or len(finishes)!=1:refuse()
    ui,usage=usages[0];fi,terminal=finishes[0]
    if (not isinstance(usage,dict) or any(type(usage.get(k)) is not int or usage[k]<0 for k in ('inputTokens','outputTokens','totalTokens'))
            or usage['totalTokens'] != usage['inputTokens']+usage['outputTokens']
            or data.get('usage') != usage or terminal.get('reason') != {'kind':'stop'}
            or fi != len(streams)-1 or ui>=fi
            or any(i>=ui for i,c in chunks if c.get('type')=='block-end')
            or list(closed.values()) != blocks):refuse()
    observed=next(f for f in facts if f.kind=='usage')
    if (usage['inputTokens'],usage['outputTokens']) != (observed.usage_input_tokens,observed.usage_output_tokens):refuse()
    if not require_settlement:return
    if any(len([f for f in facts if f.kind==k]) != 1 for k in ('terminal','settlement')):refuse()
    evidence=store.read_json(read(next(f for f in facts if f.kind=='terminal').evidence_ref))
    if (evidence != {'schema_version':'DshRejectedTextFinishObservationV1','request_digest':finish['request_digest'],
                     'finish_reason':'stop','stream_complete':True,'raw_ref':finish['raw_ref'],'session_ref':finish['session_ref']}
            or next(f for f in facts if f.kind=='terminal').evidence_ref != next(f for f in facts if f.kind=='settlement').evidence_ref):
        refuse()
