"""Read-only proof of historical text stop archived at natural fetch EOF.

This module neither mints native tool/execute sources nor mutates fees/tasks.
A reviewed operator recovery must additionally bind the exact producer, original
request/claim/ledger/grant and transaction plan before consuming this proof.
"""
from .legacy_retirement import json_object
from .protocol import ProtocolError


def refuse():
    raise ProtocolError('historical_text_stop_transport_unproven')


def verify_text_stop_stream(raw, model):
    lines=[line for line in raw.splitlines() if line]
    if (not lines or lines[-1] != b'data: [DONE]' or sum(l==b'data: [DONE]' for l in lines)!=1
            or any(not l.startswith(b'data: ') for l in lines)):
        refuse()
    events=[json_object(line[6:]) for line in lines[:-1]]
    if (not events or len({e.get('id') for e in events})!=1
            or any(not isinstance(e.get('id'),str) or not e['id'] or e.get('model')!=model for e in events)):
        refuse()
    content=[];reasoning=[];usage=[];finished=False;finish_at=None;usage_at=None
    for position,event in enumerate(events):
        choices=event.get('choices')
        if not isinstance(choices,list) or len(choices)>1 or (finished and choices):refuse()
        if event.get('usage') is not None:
            usage.append(event['usage']);usage_at=position
        for c in choices:
            if not isinstance(c,dict) or type(c.get('index')) is not int or c['index']!=0:refuse()
            delta=c.get('delta')
            if (not isinstance(delta,dict) or set(delta)-{'role','content','reasoning','reasoning_content'}
                    or ('role' in delta and delta['role']!='assistant')
                    or ('reasoning' in delta and 'reasoning_content' in delta)):refuse()
            for name,target in (('content',content),('reasoning',reasoning),('reasoning_content',reasoning)):
                if name in delta:
                    if not isinstance(delta[name],str):refuse()
                    target.append(delta[name])
            if c.get('finish_reason') is not None:
                if c['finish_reason']!='stop' or finished:refuse()
                finished=True;finish_at=position
    if (not finished or len(usage)!=1 or not isinstance(usage[0],dict)
            or usage_at < finish_at
            or any(type(usage[0].get(k)) is not int for k in ('prompt_tokens','completion_tokens','total_tokens'))
            or usage[0]['prompt_tokens']<=0 or usage[0]['completion_tokens']<0
            or usage[0]['total_tokens']!=usage[0]['prompt_tokens']+usage[0]['completion_tokens']):refuse()
    return ''.join(content),''.join(reasoning),usage[0]


def verify_failed_text_session(raw, session_id, text, reasoning, usage, error_message):
    rows=[json_object(line) for line in raw.splitlines() if line]
    if (not rows or rows[0].get('type')!='session' or rows[0].get('version')!=4
            or rows[0].get('id')!=session_id
            or any(type(r.get('seq')) is not int for r in rows[1:])
            or any(a['seq']>=b['seq'] for a,b in zip(rows[1:],rows[2:]))
            or any(r.get('type') in {'assistant/message','tool/call','tool/result'} for r in rows)):
        refuse()
    attempts=[r for r in rows if r.get('type')=='assistant/attempt']
    if len(attempts)!=1 or not isinstance(error_message,str) or not error_message:refuse()
    event=attempts[0];data=event.get('data')
    if (not isinstance(data,dict) or type(data.get('turn')) is not int or type(data.get('step')) is not int
            or not isinstance(data.get('stream'),list)):refuse()
    records=data['stream'];opened={};parts={};chunks=[];seen_usage=False
    for i,s in enumerate(records):
        if not isinstance(s,dict):refuse()
        if s.get('type') in {'text-chunks','reasoning-chunks'}:
            bi=s.get('index');dt=s.get('dt');values=s.get('texts');kind='text' if s['type']=='text-chunks' else 'reasoning'
            if (type(bi) is not int or opened.get(bi)!=kind or seen_usage
                    or not isinstance(values,list) or any(not isinstance(v,str) for v in values)
                    or not isinstance(dt,list) or len(dt)!=len(values)-1
                    or any(type(v) is not int or v<0 for v in dt)):refuse()
            parts.setdefault(bi,[]).extend(values)
        elif s.get('type')=='chunk' and isinstance(s.get('chunk'),dict):
            c=s['chunk'];chunks.append((i,c))
            if c.get('type')=='block-start':
                bi=c.get('index');kind=c.get('blockType')
                if type(bi) is not int or bi<0 or bi in opened or seen_usage or kind not in {'text','reasoning'}:refuse()
                opened[bi]=kind
            elif c.get('type')=='usage':seen_usage=True
            elif c.get('type')!='finish':refuse()
        else:refuse()
    def join(kind):return ''.join(v for bi,bt in opened.items() if bt==kind for v in parts.get(bi,[]))
    if join('text')!=text or join('reasoning')!=reasoning:refuse()
    used=[(i,c) for i,c in chunks if c.get('type')=='usage'];finished=[(i,c) for i,c in chunks if c.get('type')=='finish']
    failure={'code':'PI_AI_ERROR','message':error_message}
    if (len(used)!=1 or len(finished)!=1 or not used[0][0]<finished[0][0]==len(records)-1
            or used[0][1].get('usage') != {'inputTokens':usage['prompt_tokens'],'outputTokens':usage['completion_tokens'],'totalTokens':usage['total_tokens']}
            or finished[0][1].get('reason') != {'kind':'error','failure':failure}):refuse()
    bound={}
    for kind in ('turn/start','step/start','step/end','turn/end'):
        found=[r for r in rows if r.get('type')==kind]
        if (len(found)!=1 or not isinstance(found[0].get('data'),dict)
                or type(found[0]['data'].get('turn')) is not int
                or found[0]['data'].get('turn') != data['turn']
                or (kind.startswith('step/') and (type(found[0]['data'].get('step')) is not int or found[0]['data'].get('step') != data['step']))):refuse()
        bound[kind]=found[0]
    if (not bound['turn/start']['seq']<bound['step/start']['seq']<event['seq']<bound['step/end']['seq']<bound['turn/end']['seq']
            or bound['turn/end']['data'].get('reason') != {'kind':'error','error':failure}):refuse()
    return rows
