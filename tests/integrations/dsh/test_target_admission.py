"""Unit contracts for original read-only fresh-target authority and lifecycle."""
from copy import deepcopy
from pathlib import Path
import sqlite3

import pytest
from code2paper.agentic.digest import digest_json
from code2paper.integrations.dsh.artifacts import ArtifactStore, TaskScope
from code2paper.integrations.dsh.protocol import ProtocolError
from code2paper.integrations.dsh.target_admission import (
    CONFIG_KEYS, LOCAL_FILES, STABLE_FILES, TREES, runtime_authority_projection,
)
from code2paper.integrations.dsh.task_store import SerialBackendAdmission, TaskStore


def projection_input(root):
    # Projection UNIT input, never a full certificate or executable receipt.
    config={key:'unit:'+key for key in CONFIG_KEYS}
    config['options']={'maxTokens':4096,'temperature':0.2}
    files={key:{'path':str(root/key),'resolved_path':str(root/key),
        'digest':digest_json(key),'symlink':None} for key in STABLE_FILES | LOCAL_FILES}
    trees={key:{'path':str(root/key),'resolved_path':str(root/key),'symlink':None,
        'digest':digest_json(key),'entries':[]} for key in TREES}
    composition={'engine_digest':digest_json('engine'),'validator_digest':digest_json('validator'),
        'files':files,'trees':trees,'effective_config':config,'upstream_source_sha':None}
    bootstrap={'composition':composition,'composition_spec':{'files':{key:value['path'] for key,value in files.items()},
        'trees':{key:value['path'] for key,value in trees.items()},'effective_config':config}}
    launch={'initialize':{'protocol_version':'c2p-dsh/1','schema_digest':digest_json('rpc'),
        'max_frame_bytes':1048576,'validator_digest':composition['validator_digest']},
        'provider_config':{'providers':{'offline':{'baseURL':'http://127.0.0.1:12345/v1'}}}}
    return bootstrap,launch


def test_projection_allows_only_enumerated_fresh_local_material(tmp_path):
    bootstrap,launch=projection_input(tmp_path)
    changed=deepcopy(bootstrap)
    changed['composition_spec']['effective_config']['backend_state_root']='unit:fresh/backend'
    for key in LOCAL_FILES:
        changed['composition_spec']['files'][key]=str(tmp_path/'fresh'/key)
        changed['composition']['files'][key]={'path':str(tmp_path/'fresh'/key),
            'resolved_path':str(tmp_path/'fresh'/key),'digest':digest_json('new:'+key),'symlink':None}
    assert runtime_authority_projection(bootstrap,launch,'candidate') == runtime_authority_projection(changed,launch,'candidate')


@pytest.mark.parametrize('key',sorted(STABLE_FILES))
def test_every_stable_file_entry_is_authority(tmp_path,key):
    bootstrap,launch=projection_input(tmp_path)
    changed=deepcopy(bootstrap)
    changed['composition']['files'][key]['digest']=digest_json('changed')
    assert runtime_authority_projection(bootstrap,launch,'candidate') != runtime_authority_projection(changed,launch,'candidate')


@pytest.mark.parametrize('kind,key',[('files','unknown'),('trees','unknown'),('effective_config','unknown')])
def test_unknown_authority_keys_fail_closed(tmp_path,kind,key):
    bootstrap,launch=projection_input(tmp_path)
    bootstrap['composition_spec'][kind][key]='unqualified'
    with pytest.raises(ProtocolError,match='target_authority_schema_invalid'):
        runtime_authority_projection(bootstrap,launch,'candidate')


@pytest.mark.parametrize('kind', ['model','options','backend_resource_key','provider','tree','symlink'])
def test_model_routes_options_trees_and_links_remain_authority(tmp_path,kind):
    bootstrap,launch=projection_input(tmp_path)
    changed=deepcopy(bootstrap);new_launch=deepcopy(launch)
    if kind in ('model','options','backend_resource_key'):
        changed['composition_spec']['effective_config'][kind]='changed'
    elif kind == 'provider':new_launch['provider_config']['providers']['offline']['baseURL']='http://127.0.0.1:54321/v1'
    elif kind == 'tree':changed['composition']['trees']['runtime']['entries']=[{'path':'new','digest':digest_json('new')}]
    else:changed['composition']['files']['loader']['symlink']='different'
    assert runtime_authority_projection(bootstrap,launch,'candidate') != runtime_authority_projection(changed,new_launch,'candidate')


def inventory(root):
    return {str(path.relative_to(root)):path.read_bytes() for path in root.rglob('*') if path.is_file()}


def test_readonly_original_artifact_store_cannot_create_or_put(tmp_path):
    scope=TaskScope('execution:fresh','task:writer',0)
    with pytest.raises(FileNotFoundError):ArtifactStore.open_readonly(tmp_path/'absent',scope)
    assert not (tmp_path/'absent').exists()
    active=ArtifactStore(tmp_path/'run',scope);ref=active.put_json({'original':'immutable'})
    before=inventory(tmp_path)
    observer=ArtifactStore.open_readonly(tmp_path/'run',scope)
    assert observer.read_json(ref) == {'original':'immutable'}
    with pytest.raises(ProtocolError,match='artifact_readonly'):observer.put_json({'new':'forbidden'})
    assert inventory(tmp_path) == before


def test_original_initial_task_observation_preserves_files_and_refuses_prepared(tmp_path):
    scope=TaskScope('execution:fresh','task:writer',0)
    active=TaskStore(tmp_path/'run',scope)
    before=inventory(tmp_path)
    observer=TaskStore.observe_initial(active.root,scope)
    assert observer.root == active.root and observer.scope == scope
    assert inventory(tmp_path) == before
    with pytest.raises(ProtocolError,match='task_store_identity_mismatch'):
        TaskStore.observe_initial(active.root,TaskScope('execution:other','task:writer',0))
    with sqlite3.connect(active.path) as db:
        db.execute('INSERT INTO tasks (task_key,payload,started_ms,state) VALUES (?,?,?,?)',('other',b'{}',1,'outbox'))
    before=inventory(tmp_path)
    with pytest.raises(ProtocolError,match='target_task_already_prepared'):TaskStore.observe_initial(active.root,scope)
    assert inventory(tmp_path) == before


def test_original_backend_observation_allows_empty_or_exact_owner_only(tmp_path):
    active=SerialBackendAdmission(tmp_path/'backend','provider:offline')
    before=inventory(tmp_path)
    observer,binding=SerialBackendAdmission.observe_initial(active.root,active.resource_key,
        execution_id='execution:fresh',run_root=tmp_path/'run')
    assert binding == {'state':'empty','owner':None}
    assert inventory(tmp_path) == before
    actual=active.acquire(execution_id='execution:fresh',run_root=tmp_path/'run')
    before=inventory(tmp_path)
    _,binding=SerialBackendAdmission.observe_initial(active.root,active.resource_key,
        execution_id='execution:fresh',run_root=tmp_path/'run')
    assert binding == {'state':'owned','owner':actual}
    assert inventory(tmp_path) == before
    with pytest.raises(ProtocolError,match='backend_run_admission_held'):
        SerialBackendAdmission.observe_initial(active.root,active.resource_key,
            execution_id='execution:other',run_root=tmp_path/'run')
    other=SerialBackendAdmission(active.root,'provider:other')
    other.acquire(execution_id='execution:other',run_root=tmp_path/'other')
    with pytest.raises(ProtocolError,match='backend_run_admission_held'):
        SerialBackendAdmission.observe_initial(active.root,active.resource_key,
            execution_id='execution:fresh',run_root=tmp_path/'run')


@pytest.mark.parametrize('mutation',['none','config','launcher','overlay','escape','symlink'])
def test_local_transport_only_certified_relocation(tmp_path,mutation):
    from types import SimpleNamespace
    from code2paper.agentic.digest import canonical_json_bytes
    from code2paper.integrations.dsh.target_admission import validate_local_transport
    roots=[tmp_path/'qualified',tmp_path/'target'];specs=[]
    for root in roots:
        root.mkdir()
        files={key:root/key for key in LOCAL_FILES}
        files['host_config'].write_bytes(b'certified profile bytes')
        files['test_worker_launcher'].write_bytes(b'#!/bin/sh\nexec python guard '+str(root/'python-sentinel.json').encode()+b' "$@"\n')
        files['host_overlay'].write_bytes(canonical_json_bytes([
            {'id':'web-runtime','config':{'printUrl':False,'openBrowser':False,'surfaceContext':False,'trustedHosts':[]}},
            {'id':'session-persistence-jsonl','config':{'root':str(root/'sessions'),'compression':'none'}}]))
        specs.append(SimpleNamespace(files=files))
    if mutation == 'config':specs[1].files['host_config'].write_bytes(b'arbitrary unqualified config')
    elif mutation == 'launcher':specs[1].files['test_worker_launcher'].write_bytes(b'#!/bin/sh\nexit 0\n')
    elif mutation == 'overlay':specs[1].files['host_overlay'].write_bytes(b'[]')
    elif mutation == 'escape':specs[1].files['host_config']=specs[0].files['host_config']
    elif mutation == 'symlink':
        path=specs[1].files['host_config'];path.unlink();path.symlink_to(specs[0].files['host_config'])
    if mutation == 'none':validate_local_transport(*specs,*roots)
    else:
        with pytest.raises(ProtocolError):validate_local_transport(*specs,*roots)
