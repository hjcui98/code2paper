"""Historical EOF text proof never accepts an output or invents a tool call."""
from copy import deepcopy
import json
import pytest
from code2paper.integrations.dsh.protocol import ProtocolError
from code2paper.integrations.dsh.text_stop_transport_proof import verify_text_stop_stream,verify_failed_text_session


def frames():
    def frame(choices,usage=None):
        v={'id':'reply:fixture','model':'fixture-model','choices':choices}
        if usage is not None:v['usage']=usage
        return v
    def choice(delta,finish=None):return {'index':0,'delta':delta,'finish_reason':finish}
    return [frame([choice({'role':'assistant','content':''})]),frame([choice({'reasoning':'Private thought.'})]),
        frame([choice({'content':'```json\n{"ordinary":"文🙂"}\n```'},'stop')]),
        frame([],{'prompt_tokens':7,'completion_tokens':9,'total_tokens':16})]


def encode(events,done=True):
    return ('\n'.join('data: '+json.dumps(e,ensure_ascii=False) for e in events)+('\ndata: [DONE]\n' if done else '\n')).encode()


def session(text,reasoning,usage):
    error='fixture observer rejected native text finish at natural EOF'
    failure={'code':'PI_AI_ERROR','message':error}
    stream=[{'type':'chunk','chunk':{'type':'block-start','index':0,'blockType':'reasoning'}},
        {'type':'reasoning-chunks','index':0,'texts':[reasoning],'dt':[]},
        {'type':'chunk','chunk':{'type':'block-start','index':1,'blockType':'text'}},
        {'type':'text-chunks','index':1,'texts':[text],'dt':[]},
        {'type':'chunk','chunk':{'type':'usage','usage':{'inputTokens':usage['prompt_tokens'],
            'outputTokens':usage['completion_tokens'],'totalTokens':usage['total_tokens']}}},
        {'type':'chunk','chunk':{'type':'finish','reason':{'kind':'error','failure':failure}}}]
    def row(seq,kind,data):return {'seq':seq,'type':kind,'data':data}
    rows=[{'type':'session','version':4,'id':'session:text'},row(1,'turn/start',{'turn':1}),
        row(2,'step/start',{'turn':1,'step':1}),row(3,'assistant/attempt',{'turn':1,'step':1,'stream':stream}),
        row(4,'step/end',{'turn':1,'step':1}),row(5,'turn/end',{'turn':1,'reason':{'kind':'error','error':failure}})]
    return rows,error


def session_bytes(rows):return b'\n'.join(json.dumps(r,ensure_ascii=False).encode() for r in rows)


def test_historical_plain_text_proof_does_not_parse_the_fenced_json():
    text,reasoning,usage=verify_text_stop_stream(encode(frames()),'fixture-model')
    rows,error=session(text,reasoning,usage)
    assert verify_failed_text_session(session_bytes(rows),'session:text',text,reasoning,usage,error)==rows
    assert text.startswith('```json')


@pytest.mark.parametrize('damage',['missing_done','duplicate_done','extra_after_done','invalid_json','wrong_model','wrong_id',
    'tool','choice_index','boolean_index','multi_choice','missing_finish','duplicate_finish','length_finish','after_finish',
    'missing_usage','duplicate_usage','bad_total','bool_usage','negative_usage','wrong_role','delta_null','content_null',
    'reasoning_aliases','usage_before_finish'])
def test_sse_damages_are_not_natural_text_completion(damage):
    es=frames();done=True;tail=b''
    if damage=='missing_done':done=False
    elif damage=='duplicate_done':tail=b'data: [DONE]\n'
    elif damage=='extra_after_done':tail=b'data: {}\n'
    elif damage=='invalid_json':tail=b'data: {\n'
    elif damage=='wrong_model':es[1]['model']='other'
    elif damage=='wrong_id':es[1]['id']='other'
    elif damage=='tool':es[1]['choices'][0]['delta']={'tool_calls':[]}
    elif damage=='choice_index':es[1]['choices'][0]['index']=1
    elif damage=='boolean_index':es[1]['choices'][0]['index']=False
    elif damage=='multi_choice':es[1]['choices'].append(deepcopy(es[1]['choices'][0]))
    elif damage=='missing_finish':es[2]['choices'][0]['finish_reason']=None
    elif damage=='duplicate_finish':es.insert(3,deepcopy(es[2]))
    elif damage=='length_finish':es[2]['choices'][0]['finish_reason']='length'
    elif damage=='after_finish':es.insert(3,deepcopy(es[1]))
    elif damage=='missing_usage':es[-1].pop('usage')
    elif damage=='duplicate_usage':es.append(deepcopy(es[-1]))
    elif damage=='bad_total':es[-1]['usage']['total_tokens']=17
    elif damage=='bool_usage':es[-1]['usage']['prompt_tokens']=True
    elif damage=='negative_usage':es[-1]['usage']['completion_tokens']=-1
    elif damage=='wrong_role':es[0]['choices'][0]['delta']['role']='user'
    elif damage=='delta_null':es[1]['choices'][0]['delta']=None
    elif damage=='content_null':es[2]['choices'][0]['delta']['content']=None
    elif damage=='reasoning_aliases':es[1]['choices'][0]['delta']['reasoning_content']='other'
    elif damage=='usage_before_finish':es[0]['usage']=es[-1].pop('usage')
    with pytest.raises(ProtocolError):verify_text_stop_stream(encode(es,done)+tail,'fixture-model')


@pytest.mark.parametrize('damage',['wrong_session','wrong_version','seq_duplicate','seq_reverse','missing_attempt',
    'duplicate_attempt','tool_call','assistant_message','wrong_text','wrong_reasoning','delta_index','delta_bool',
    'delta_changed','dt_bool','usage_missing','usage_duplicate','usage_wrong','finish_missing','finish_duplicate',
    'finish_stop','different_error','missing_end','wrong_turn','end_completed','block_end','delta_after_usage'])
def test_old_session_damage_cannot_be_reinterpreted_as_execute_completion(damage):
    text,reasoning,usage=verify_text_stop_stream(encode(frames()),'fixture-model');rows,error=session(text,reasoning,usage)
    data=rows[3]['data'];stream=data['stream']
    if damage=='wrong_session':rows[0]['id']='other'
    elif damage=='wrong_version':rows[0]['version']=3
    elif damage=='seq_duplicate':rows[4]['seq']=3
    elif damage=='seq_reverse':rows[4]['seq']=2
    elif damage=='missing_attempt':rows.pop(3)
    elif damage=='duplicate_attempt':rows.insert(4,deepcopy(rows[3]))
    elif damage=='tool_call':rows.insert(4,{'type':'tool/call','seq':3,'data':{}})
    elif damage=='assistant_message':rows[3]['type']='assistant/message'
    elif damage=='wrong_text':text+='changed'
    elif damage=='wrong_reasoning':reasoning+='changed'
    elif damage=='delta_index':stream[3]['index']=0
    elif damage=='delta_bool':stream[3]['index']=True
    elif damage=='delta_changed':stream[3]['texts'][0]+='changed'
    elif damage=='dt_bool':stream[3]['dt']=[True]
    elif damage=='usage_missing':stream.pop(4)
    elif damage=='usage_duplicate':stream.insert(4,deepcopy(stream[4]))
    elif damage=='usage_wrong':stream[4]['chunk']['usage']['inputTokens']=8
    elif damage=='finish_missing':stream.pop()
    elif damage=='finish_duplicate':stream.append(deepcopy(stream[-1]))
    elif damage=='finish_stop':stream[-1]['chunk']['reason']={'kind':'stop'}
    elif damage=='different_error':error+='other'
    elif damage=='missing_end':rows.pop()
    elif damage=='wrong_turn':data['turn']=2
    elif damage=='end_completed':rows[-1]['data']['reason']={'kind':'completed'}
    elif damage=='block_end':stream.insert(4,{'type':'chunk','chunk':{'type':'block-end','index':1,'block':{'type':'text','text':text}}})
    elif damage=='delta_after_usage':stream[3],stream[4]=stream[4],stream[3]
    with pytest.raises(ProtocolError):verify_failed_text_session(session_bytes(rows),'session:text',text,reasoning,usage,error)
