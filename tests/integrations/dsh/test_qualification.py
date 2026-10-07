"""Offline qualifier boundaries and immutable operation evidence failures."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from code2paper.agentic.digest import digest_bytes
from code2paper.integrations.dsh import qualification as q
from code2paper.integrations.dsh.operator_evidence import read_evidence, validate_evidence_tree
from code2paper.integrations.dsh.protocol import ProtocolError


@pytest.mark.parametrize('identity',[None,{}, {'device':True,'inode':1}, {'device':1,'inode':0},
    {'device':1,'inode':2,'fake':True}])
def test_qualification_namespace_rejects_invalid_parent(identity):
    with pytest.raises(ProtocolError,match='parent_namespace_invalid'):
        q.assert_offline_qualification_namespace(identity)


def test_actual_outer_namespace_cannot_qualify():
    with pytest.raises(ProtocolError,match='network_not_isolated'):
        q.assert_offline_qualification_namespace(q.network_namespace_identity())


def test_distinct_namespace_with_external_interfaces_cannot_qualify(monkeypatch):
    monkeypatch.setattr(q,'network_namespace_identity',lambda:{'device':1,'inode':2})
    monkeypatch.setattr(Path,'read_text',lambda *_args,**_kwargs:'header\nheader\n lo: 0\n eth0: 0\n')
    with pytest.raises(ProtocolError,match='network_not_isolated'):
        q.assert_offline_qualification_namespace({'device':1,'inode':3})


def test_actual_bwrap_network_namespace_qualifies_only_loopback():
    executable=shutil.which('bwrap')
    assert executable is not None,'qualification requires the installed isolating launcher'
    parent=q.network_namespace_identity()
    root=Path(__file__).resolve().parents[3]
    code=('import sys,json;sys.path.insert(0,'+repr(str(root/'src'))+');'
          'from code2paper.integrations.dsh.qualification import assert_offline_qualification_namespace;'
          'print(json.dumps(assert_offline_qualification_namespace('+repr(parent)+')))')
    result=subprocess.run([executable,'--ro-bind','/','/','--unshare-net','--proc','/proc','--dev','/dev',
        '--setenv','PYTHONDONTWRITEBYTECODE','1',sys.executable,'-c',code],capture_output=True,timeout=30)
    assert result.returncode == 0,result.stderr.decode()
    assert json.loads(result.stdout) != parent


@pytest.mark.parametrize('url',['http://localhost:8006/v1','http://10.0.0.1:8006/v1',
    'http://127.0.0.1/v1','http://user:password@127.0.0.1:8006/v1',
    'http://127.0.0.1:8006/v1?key=value','http://127.0.0.1:8006/#x',
    'file:///tmp/provider','http://[::1]:invalid/v1'])
def test_qualification_route_rejects_dns_external_or_credentials(url):
    with pytest.raises(ProtocolError,match='provider_not_loopback'):
        q.assert_frozen_loopback_provider({'provider_config':{'providers':{'custom':{'baseURL':url}}}})


def test_qualification_checks_every_provider():
    launch={'provider_config':{'providers':{'first':{'baseURL':'http://127.0.0.1:1234/v1'},
        'second':{'baseURL':'http://[::1]:4321/v1'}}}}
    q.assert_frozen_loopback_provider(launch)
    launch['provider_config']['providers']['second']['baseURL']='https://example.com:443/v1'
    with pytest.raises(ProtocolError,match='provider_not_loopback'):q.assert_frozen_loopback_provider(launch)


def _binding(path):
    raw=path.read_bytes()
    return {'path':str(path),'bytes_digest':digest_bytes(raw),'byte_length':len(raw)}


def test_operation_evidence_requires_full_bound_bytes_and_owned_path(tmp_path):
    path=tmp_path/'result.json';path.write_bytes(b'{}')
    binding=_binding(path)
    assert read_evidence(binding,path) == b'{}'
    path.write_bytes(b'{}tamper')
    with pytest.raises(ProtocolError,match='bytes_changed'):read_evidence(binding,path)
    path.write_bytes(b'{}')
    outside=tmp_path/'other';outside.write_bytes(b'{}')
    with pytest.raises(ProtocolError,match='binding_invalid'):read_evidence(binding,outside)
    link=tmp_path/'link';link.symlink_to(path)
    with pytest.raises(ProtocolError,match='binding_invalid'):read_evidence({**binding,'path':str(link)},link)
    path.unlink()
    with pytest.raises(FileNotFoundError):read_evidence(binding,path)


def test_original_reader_dependencies_require_exact_tree_membership(tmp_path):
    root=tmp_path/'run';root.mkdir();first=root/'receipt.json';first.write_bytes(b'{}')
    empty=root/'lease';empty.write_bytes(b'')
    bindings=[_binding(file) for file in sorted(root.iterdir())]
    validate_evidence_tree(root,bindings)
    extra=root/'unbound.json';extra.write_bytes(b'{}')
    with pytest.raises(ProtocolError,match='tree_changed'):validate_evidence_tree(root,bindings)
    extra.unlink();first.write_bytes(b'{"changed":true}')
    with pytest.raises(ProtocolError,match='bytes_changed'):validate_evidence_tree(root,bindings)
    with pytest.raises(ProtocolError,match='tree_missing'):validate_evidence_tree(root,[])


def test_original_task_observation_preserves_database_and_rejects_corruption(tmp_path):
    import sqlite3
    from code2paper.integrations.dsh.task_store import TaskStore
    from code2paper.integrations.dsh.artifacts import TaskScope
    from .test_task_recovery import prepare, SCOPE
    store,initial=prepare(tmp_path)
    claim=store.claim('host:reader-test')
    original=store.read()
    bindings=[_binding(path) for path in sorted(tmp_path.rglob('*')) if path.is_file()]
    assert TaskStore.read_persisted(tmp_path,SCOPE) == original
    assert [_binding(Path(row['path'])) for row in bindings] == bindings
    with pytest.raises(ProtocolError,match='identity_mismatch'):
        TaskStore.read_persisted(tmp_path,TaskScope('other',SCOPE.task_id,SCOPE.task_epoch))
    with sqlite3.connect(store.path) as db:db.execute("UPDATE tasks SET claim_lineage=?",(b'[]',))
    with pytest.raises(ProtocolError,match='claim_lineage_invalid'):TaskStore.read_persisted(tmp_path,SCOPE)
    missing=tmp_path/'absent'
    with pytest.raises(ProtocolError,match='task_store_observation_invalid'):TaskStore.read_persisted(missing,SCOPE)
    assert not missing.exists()
