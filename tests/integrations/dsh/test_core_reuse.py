"""Actual serial reports and source-delta rejection for offline core reuse."""
import json
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from code2paper.agentic.digest import canonical_json_bytes, digest_bytes, digest_json
from code2paper.integrations.dsh.core_reuse import (
    _validate_source_delta, validate_sequential_node_report,
)
from code2paper.integrations.dsh.offline_admission import validate_node_report
from code2paper.integrations.dsh.protocol import ProtocolError

ROOT=Path(__file__).resolve().parents[3]


@pytest.fixture
def serial_report(tmp_path):
    helper=tmp_path/'shared.mjs'
    helper.write_text("import {test} from 'node:test';\ntest('same imported name',()=>{});\n")
    entries=[]
    for name in ('one','two'):
        path=tmp_path/f'{name}.test.mjs'
        path.write_text("import './shared.mjs';\n");entries.append(str(path))
    report=tmp_path/'events.jsonl'
    command=[shutil.which('node'),'--test','--test-concurrency=1','--test-reporter=spec',
        '--test-reporter='+str(ROOT/'integrations/dsh/dev/toolchain/suite-reporter.mjs'),
        '--test-reporter-destination=stdout','--test-reporter-destination='+str(report),*entries]
    process=subprocess.run(command,cwd=tmp_path,capture_output=True,timeout=30)
    assert process.returncode == 0,process.stderr
    return report.read_bytes()


def test_imported_names_are_distinct_by_actual_entry(serial_report):
    result=validate_sequential_node_report(serial_report)
    assert result['counts']['tests'] == 2
    assert len({tuple(row) for row in result['node_ids']}) == 2
    assert result['node_ids'][0][1:] == result['node_ids'][1][1:]
    meta=json.loads(serial_report.splitlines()[0])
    with pytest.raises(ProtocolError,match='duplicate'):
        validate_node_report(serial_report,cwd=meta['cwd'],argv=meta['argv'],exec_argv=meta['execArgv'])


@pytest.mark.parametrize('field',['cwd','argv','execArgv'])
def test_serial_reader_binds_original_runner(serial_report,field):
    rows=[json.loads(line) for line in serial_report.splitlines()];meta=dict(rows[0])
    rows[0][field]='wrong' if field == 'cwd' else ['wrong']
    with pytest.raises(ProtocolError,match='runner_mismatch'):
        validate_sequential_node_report(b'\n'.join(canonical_json_bytes(row) for row in rows),
            cwd=meta['cwd'],argv=meta['argv'],exec_argv=meta['execArgv'])


def test_one_validation_cache_does_not_reuse_report_bytes_or_cross_admissions(serial_report,tmp_path,monkeypatch):
    from code2paper.integrations.dsh import core_reuse
    meta=json.loads(serial_report.splitlines()[0]);files=meta['argv'][1:]
    report=tmp_path/'bound.jsonl';report.write_bytes(serial_report)
    output=tmp_path/'output.log';output.write_bytes(b'actual native tests passed')
    suite={'suite_id':'node','argv':[meta['argv'][0],*meta['execArgv'],*files],
        'cwd':meta['cwd'],'runner':'node','report_path':str(report),
        'discovered_files':[str(Path(f).relative_to(tmp_path)) for f in files]}
    original={**{key:suite[key] for key in ('suite_id','argv','cwd','runner','report_path')},
        'report_digest':digest_bytes(serial_report),'report_bytes':len(serial_report),
        'output_path':str(output),'output_digest':digest_bytes(output.read_bytes()),'output_bytes':output.stat().st_size,
        'exit_code':0,'engine_before':'e','engine_after':'e','validator_before':'v','validator_after':'v',
        'composition_before':'c','composition_after':'c'}
    prior={'engine_root':str(tmp_path),'engine_digest':'e','validator_digest':'v','composition_digest':'c','suites':[{},suite]}
    calls=[]
    def validated(binding,plan):calls.append(binding);return None,prior,[{},original],{}
    monkeypatch.setattr(core_reuse,'_validated_manifest',validated)
    run={**{key:suite[key] for key in ('suite_id','argv','cwd','runner','report_path')},'exit_code':0,
        'output_digest':original['output_digest'],'evidence_reuse':{'path':str(tmp_path/'manifest'),'bytes_digest':'m','byte_length':1}}
    plan={'engine_root':str(tmp_path),'engine_digest':'e','validator_digest':'v','composition_digest':'c'};cache={}
    for _ in range(2):assert core_reuse.validate_reused_suite(plan,suite,run,_reuse_cache=cache)['passed_count']==2
    assert len(calls)==1
    core_reuse.validate_reused_suite(plan,suite,run)
    assert len(calls)==2
    report.write_bytes(serial_report+b' ')
    with pytest.raises(ProtocolError,match='bytes_changed'):
        core_reuse.validate_reused_suite(plan,suite,run,_reuse_cache=cache)


@pytest.mark.parametrize('damage',['missing-pass','failed','skipped','wrong-total','duplicate-in-file','missing-summary'])
def test_serial_reader_rejects_incomplete_or_failed_evidence(serial_report,damage):
    rows=[json.loads(line) for line in serial_report.splitlines()]
    index=next(i for i,row in enumerate(rows) if row.get('type') == 'test:pass')
    if damage == 'missing-pass':rows.pop(index)
    elif damage == 'failed':rows[index]['type']='test:fail'
    elif damage == 'skipped':rows[index]['skip']=True
    elif damage == 'wrong-total':rows[-1]['counts']['tests']+=1
    elif damage == 'missing-summary':rows.pop()
    else:
        enqueue=next(row for row in rows if row.get('type') == 'test:enqueue' and row.get('name') == 'same imported name')
        rows.insert(index,dict(enqueue))
    with pytest.raises(ProtocolError):
        validate_sequential_node_report(b'\n'.join(canonical_json_bytes(row) for row in rows))


def _source_case(tmp_path,monkeypatch,path,old_text,new_text,edit=None):
    from code2paper.integrations.dsh import suite_runner
    target=tmp_path/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(new_text)
    def entry(text):return {'path':path,'status':'??','kind':'file','digest':digest_bytes(text.encode())}
    old_entry=entry(old_text);current_entry=entry(new_text)
    old={'commit_sha':'baseline','entries':[old_entry]}
    old['source_digest']=digest_json({'schema_version':'1.0',**old})
    engine_digest=digest_json({'schema_version':'1.0','commit_sha':'baseline','entries':[current_entry]})
    engine=SimpleNamespace(commit_sha='baseline',source_digest=engine_digest,
        entries=[SimpleNamespace(path=path,as_payload=lambda:current_entry)])
    validator=SimpleNamespace(digest='validator')
    monkeypatch.setattr(suite_runner,'_identity',lambda root:(engine,validator))
    changed={path:{'before':old_entry,'after':current_entry}} if old_text != new_text else {}
    review={'schema_version':'OfflineCoreReuseReviewV1','decision':'VERIFICATION_ONLY','independent':True,
        'engine_digest':engine_digest,'validator_digest':'validator','changed_files':changed}
    def binding(name,value):
        raw=canonical_json_bytes(value);p=tmp_path/name;p.write_bytes(raw)
        return {'path':str(p),'bytes_digest':digest_bytes(raw),'byte_length':len(raw)}
    manifest={'source_freeze':binding('freeze.json',{'engine_snapshot':old}),
        'review':binding('review.json',review),'test_label_edits':{path:edit} if edit is not None else {}}
    plan={'engine_root':str(tmp_path),'engine_digest':engine_digest,'validator_digest':'validator'}
    return manifest,plan,review,binding


def test_documentation_delta_can_reuse_behavior(tmp_path,monkeypatch):
    manifest,plan,_,_=_source_case(tmp_path,monkeypatch,'docs/progress.md','old','new')
    _validate_source_delta(manifest,plan)


@pytest.mark.parametrize('path',['src/code2paper/llm/section_writer.py','tests/case.py','docs/config.json'])
def test_runtime_or_behavior_change_cannot_be_approved_as_identity_only(tmp_path,monkeypatch,path):
    manifest,plan,_,_=_source_case(tmp_path,monkeypatch,path,'old','new')
    with pytest.raises(ProtocolError,match='runtime_source_changed'):_validate_source_delta(manifest,plan)


def test_pure_conditional_test_label_insertion_is_proven_by_preimage(tmp_path,monkeypatch):
    old="test(`case`,async()=>{run();});\n";insertion="${mode === 'stop' ? ' with stop' : ''}"
    offset=old.index('`,');new=old[:offset]+insertion+old[offset:]
    manifest,plan,_,_=_source_case(tmp_path,monkeypatch,'integrations/dsh/tests/case.test.ts',old,new,
        {'insertion':insertion,'offset':offset})
    _validate_source_delta(manifest,plan)


@pytest.mark.parametrize('damage',['body','side-effect','review-source','review-paths'])
def test_test_label_and_review_do_not_cover_other_changes(tmp_path,monkeypatch,damage):
    old="test(`case`,async()=>{run();});\n";insertion="${mode === 'stop' ? ' with stop' : ''}"
    if damage == 'side-effect':insertion="${send() === 'stop' ? ' with stop' : ''}"
    offset=old.index('`,');new=old[:offset]+insertion+old[offset:]
    if damage == 'body':new=new.replace('run();','skip();')
    manifest,plan,review,binding=_source_case(tmp_path,monkeypatch,'integrations/dsh/tests/case.test.ts',old,new,
        {'insertion':insertion,'offset':offset})
    if damage == 'review-source':review['engine_digest']='wrong';manifest['review']=binding('bad.json',review)
    if damage == 'review-paths':review['changed_files']={};manifest['review']=binding('bad.json',review)
    with pytest.raises(ProtocolError):_validate_source_delta(manifest,plan)


def test_inventory_fast_paths_preserve_inventory_wire(tmp_path):
    import hashlib
    import os
    from code2paper.integrations.dsh.runtime_inventory import runtime_inventory
    root=tmp_path/'tree';root.mkdir();(root/'nested').mkdir()
    (root/'nested'/'file').write_bytes(b'content')
    (root/'empty').write_bytes(b'')
    (root/'internal').symlink_to('nested/file')
    (root/'directory-link').symlink_to('nested',target_is_directory=True)
    linked=tmp_path/'linked';linked.mkdir();(linked/'source').write_bytes(b'other')
    (root/'external').symlink_to(linked/'source')
    expected={}
    for here,dirs,files in os.walk(root,followlinks=False):
        for name in sorted(dirs+files):
            path=Path(here)/name;relative=path.relative_to(root).as_posix()
            if path.is_symlink():
                target=os.readlink(path);resolved=path.resolve(strict=True)
                expected[relative]={'link':target}
                if os.path.isabs(target) or not resolved.is_relative_to(root):
                    expected[relative]['resolved_path']=str(resolved)
            elif path.is_file():
                expected[relative]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'size':path.stat().st_size}
    assert runtime_inventory(root,linked_roots=(linked,)) == expected


@pytest.mark.parametrize('absolute',[False,True])
def test_fast_inventory_keeps_unscoped_symlink_rejection(tmp_path,absolute):
    from code2paper.integrations.dsh.runtime_inventory import runtime_inventory
    root=tmp_path/'tree';root.mkdir();outside=tmp_path/'outside';outside.write_bytes(b'x')
    (root/'link').symlink_to(outside if absolute else '../outside')
    with pytest.raises(ValueError,match='external_or_absolute_symlink'):
        runtime_inventory(root)
