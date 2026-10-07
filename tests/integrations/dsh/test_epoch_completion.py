"""Original Worker/fee store epoch closure using explicit UNIT Session fixtures."""
from copy import deepcopy
import pytest
from code2paper.integrations.dsh.writer_contract import ArtifactRefV1
from code2paper.integrations.dsh.task_store import SerialBackendAdmission
from .test_composition_identity import composition
from .test_step_admission import owner,observe,reserve,finish,completion_ref


def prepare_epoch(d):
    first=reserve(d,observe(d)['result']['step_ref'])['result'];finish(d,first)
    second=reserve(d,observe(d,2)['result']['step_ref'])['result'];finish(d,second,status='unfinished')
    status=d['child'].call('request.status',{**d['scope'],'contract_ref':d['contract_ref']})['result']
    final=completion_ref(d,second);evidence=d['f'].store.read_json(final)
    session=deepcopy(d['f'].store.read_json(ArtifactRefV1.model_validate(evidence['session_ref'])))
    session['events'].append({'seq':session['events'][-1]['seq']+1,'type':'turn/end','data':{'turn':1,'reason':{'kind':'completed'}}})
    value={'schema_version':'DshEpochProviderQuiescenceV2',**d['scope'],'session_id':evidence['session_id'],
        'source':'gated-adapter-epoch-natural-exhaustion/2','session_ref':d['f'].store.put_json(session).model_dump(mode='json'),
        'steps':[*status['completed_step_refs'],final.model_dump(mode='json')]}
    return second,final,value,session


def test_original_epoch_owner_releases_only_after_every_request_settles(owner):
    d=owner;second,final,value,_=prepare_epoch(d);ref=d['f'].store.put_json(value).model_dump(mode='json')
    result=d['child'].call('backend.observe_quiescence',{**d['scope'],'quiescence_ref':ref});assert 'result' in result,result
    result=d['child'].call('backend.release',{**d['scope'],'quiescence_ref':ref})
    assert result['error']['message']=='backend_release_task_open'
    assert 'result' in d['child'].call('task.cancel',{**d['scope'],'claim':d['claim']})
    result=d['child'].call('backend.release',{**d['scope'],'quiescence_ref':ref})
    assert result['error']['message']=='backend_release_accounting_unsettled'
    for kind in ('terminal','settlement'):
        result=d['child'].call('request.settle',{**d['scope'],'contract_ref':d['contract_ref'],'reservation':second,
            'kind':kind,'event_id':'last:'+kind,'evidence_ref':final.model_dump(mode='json')});assert 'result' in result,result
    result=d['child'].call('backend.release',{**d['scope'],'quiescence_ref':ref});assert 'result' in result,result
    release=result['result'];assert release['schema_version']=='DshEpochSerialBackendReleaseV2'
    admission=d['f'].backend_admission
    assert SerialBackendAdmission.read_persisted(admission.root,admission.resource_key)['state']=='empty'
    assert d['child'].call('backend.release',{**d['scope'],'quiescence_ref':ref})['result']==release


@pytest.mark.parametrize('damage',['omitted-step','order','source','missing-end','session-prefix'])
def test_epoch_proof_damage_keeps_original_owner_and_pending_fees(owner,damage):
    d=owner;_,_,value,session=prepare_epoch(d)
    if damage=='omitted-step':value['steps'].pop(0)
    if damage=='order':value['steps'].reverse()
    if damage=='source':value['source']='model-says-idle'
    if damage=='missing-end':session['events'].pop();value['session_ref']=d['f'].store.put_json(session).model_dump(mode='json')
    if damage=='session-prefix':session['events'][0]['data']['turn']=2;value['session_ref']=d['f'].store.put_json(session).model_dump(mode='json')
    ref=d['f'].store.put_json(value).model_dump(mode='json')
    result=d['child'].call('backend.observe_quiescence',{**d['scope'],'quiescence_ref':ref});assert 'error' in result,result
    assert observe(d,3)['error']['message']=='dsh_epoch_has_unsettled_request'
    admission=d['f'].backend_admission
    assert SerialBackendAdmission.read_persisted(admission.root,admission.resource_key)['state']=='owned'
