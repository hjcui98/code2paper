"""Gate-H regressions exercise production activation, setup and audit owners."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

REPO = Path(__file__).resolve().parents[4]


def load_dev():
    spec = importlib.util.spec_from_file_location('gate_h_dev', REPO / 'scripts/dsh_dev.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def installation(tmp_path):
    m = load_dev()
    repo = tmp_path / 'repo'
    pkg = repo / 'integrations/dsh'
    pkg.mkdir(parents=True)
    shutil.copytree(REPO / 'integrations/dsh/dev/toolchain', pkg / 'dev/toolchain', ignore=shutil.ignore_patterns('build'))
    for file in ('package.json', 'package-lock.json'):
        shutil.copy2(REPO / 'integrations/dsh' / file, pkg / file)
    shutil.copytree(REPO / 'integrations/dsh/node_modules', pkg / 'node_modules', symlinks=True,
                    ignore=shutil.ignore_patterns('@deepseek-ai'))
    (repo / 'scripts').mkdir()
    shutil.copy2(REPO / 'scripts/dsh_dev.py', repo / 'scripts/dsh_dev.py')
    inventory_source = Path('src/code2paper/integrations/dsh/runtime_inventory.py')
    (repo / inventory_source).parent.mkdir(parents=True)
    shutil.copy2(REPO / inventory_source, repo / inventory_source)
    m.REPO = repo
    m.BUNDLE_PACKAGE = pkg
    m.DEV = repo / '.dsh-dev'
    m.CANDIDATE_ROOT = m.DEV / 'candidates'
    base = m.CANDIDATE_ROOT / '0.2.0-rc.1'
    runtime = base / 'runtime'
    for rel in m.LOOP_ORIGIN_TOUCHED:
        if rel.endswith('dispatch-origin.c2p.d.ts'):
            continue
        path = runtime / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('pristine\n')
    path = runtime / 'node_modules/@deepseek-ai/dsh/package.json'
    path.parent.mkdir(parents=True)
    path.write_text('{"version":"0.2.0-rc.1"}')
    (path.parent / 'lib').mkdir()
    (path.parent / 'lib/bin.js').write_text('// CLI fixture')
    (runtime / 'package-lock.json').write_text('{}')
    node = shutil.which('node')
    manifest = {'dsh_version':'0.2.0-rc.1', 'source_kind':'npm-registry-install',
        'runtime_tree_sha256':m.tree_digest(m.inventory(runtime)),
        'package_lock_sha256':m.digest_file(runtime / 'package-lock.json'),
        'cli_sha256':m.digest_file(runtime / m.CLI_REL),
        'node':node, 'node_version':subprocess.check_output([node, '--version'], text=True).strip()}
    m.write_json(base / 'manifest.json', manifest)
    targets = []
    for cid in ('0.2.0-rc.1+loop-origin.1', '0.2.0-rc.1+loop-origin.1-built'):
        root = m.CANDIDATE_ROOT / cid
        shutil.copytree(runtime, root / 'runtime')
        for rel in m.LOOP_ORIGIN_TOUCHED:
            (root / 'runtime' / rel).write_text('patched\n')
        obj = {**manifest, 'dsh_version':cid, 'source_kind':'local-patched',
            'upstream_dsh_version':'0.2.0-rc.1', 'base_runtime_tree_sha256':manifest['runtime_tree_sha256'],
            'runtime_tree_sha256':m.tree_digest(m.inventory(root / 'runtime')),
            'loop_origin_patch':{'touched':m.LOOP_ORIGIN_TOUCHED}}
        m.write_json(root / 'manifest.json',obj)
        targets.append(root)
    contract = {'dsh':{'base_runtime_tree_sha256':manifest['runtime_tree_sha256'],
        'runtime_tree_sha256':obj['runtime_tree_sha256'], 'patch':{'touched':m.LOOP_ORIGIN_TOUCHED,
        'source':{'build_verification_tree_sha256':obj['runtime_tree_sha256']}}}}
    m.write_json(pkg / 'compatibility.0.2.0-rc.1+loop-origin.1.json',contract)
    # Bootstrap only the test fixture's receipts from the real installed receipt.
    recorded = json.loads((REPO / '.dsh-dev/candidates/0.2.0-rc.1+loop-origin.1/toolchain.json').read_text())
    for root in targets:
        obj = m.read_json(root / 'manifest.json')
        state = {**recorded, 'peer_link_target':str(root / 'runtime/node_modules/@deepseek-ai'),
            'frozen_runtime':{k:obj[k] for k in ('dsh_version','runtime_tree_sha256','package_lock_sha256','node_version')}}
        m.write_json(root / 'toolchain.json',state)
    peer = pkg / 'node_modules/@deepseek-ai'
    peer.symlink_to(targets[0] / 'runtime/node_modules/@deepseek-ai')
    return m, pkg, base, targets, peer


def invoke(pkg, root, action='activate'):
    env = {**os.environ, 'C2P_DSH_CANDIDATE':root.name, 'C2P_DSH_DEV_ROOT':str(root), 'PYTHONDONTWRITEBYTECODE':'1'}
    return subprocess.run(['node',str(pkg / 'dev/toolchain/toolchain.mjs'),action],env=env,capture_output=True,text=True,timeout=40)


@pytest.mark.parametrize('damage', ['compiler','lock','missing_receipt','missing_target_receipt','bad_node','bad_runtime','bad_identity','missing_node_executable','different_node_bytes','write_failure'])
def test_actual_activation_failure_preserves_link_and_receipts(installation, damage):
    m,pkg,base,targets,peer = installation
    first,target=targets
    if damage == 'compiler':
        with (pkg / 'node_modules/typescript/lib/typescript.js').open('a') as stream: stream.write('// drift\n')
    elif damage == 'lock':
        with (pkg / 'package-lock.json').open('a') as stream: stream.write('\n')
    elif damage == 'missing_receipt': (first / 'toolchain.json').unlink()
    elif damage == 'missing_target_receipt': (target / 'toolchain.json').unlink()
    elif damage in ('bad_node','bad_identity'):
        obj=m.read_json(target / 'manifest.json')
        obj['node_version' if damage=='bad_node' else 'dsh_version']='wrong'
        m.write_json(target / 'manifest.json',obj)
    elif damage in ('missing_node_executable', 'different_node_bytes'):
        obj=m.read_json(target / 'manifest.json')
        obj['node']=str(target / 'wrong-node')
        if damage == 'different_node_bytes':
            fake=Path(obj['node']);fake.write_text('#!/bin/sh\necho '+obj['node_version']+'\n');fake.chmod(0o755)
        m.write_json(target / 'manifest.json',obj)
    elif damage == 'bad_runtime': (target / 'runtime/package-lock.json').write_text('drift')
    elif damage == 'write_failure':
        # Force a failing rename after link commit with a preload wrapping fs.
        hook=pkg / 'deny-rename.mjs'
        hook.write_text("import fs from 'node:fs/promises'; import {syncBuiltinESMExports} from 'node:module'; const rename=fs.rename; fs.rename=async (a,b)=>{if(b.endsWith('toolchain.json')) throw new Error('injected receipt commit failure'); return rename(a,b)}; syncBuiltinESMExports();\n")
    receipts={p:(p.read_bytes() if p.exists() else None) for p in [r / 'toolchain.json' for r in targets]}
    before=os.readlink(peer)
    if damage == 'write_failure':
        env={**os.environ,'C2P_DSH_CANDIDATE':target.name,'C2P_DSH_DEV_ROOT':str(target)}
        result=subprocess.run(['node','--import',str(hook),str(pkg / 'dev/toolchain/toolchain.mjs'),'activate'],env=env,capture_output=True,text=True,timeout=40)
    else: result=invoke(pkg,target)
    assert result.returncode != 0, result.stdout
    if damage == 'write_failure': assert 'injected receipt commit failure' in result.stderr
    if damage != 'write_failure':
        m.select_candidate(target.name)
        with pytest.raises(RuntimeError): m.activate_candidate()
    assert os.readlink(peer)==before
    assert receipts=={p:(p.read_bytes() if p.exists() else None) for p in receipts}
    assert not list(peer.parent.glob('@deepseek-ai.activate-*'))
    assert not list(target.glob('toolchain.json.activate-*'))


def test_actual_activation_and_python_wrapper_switch_both_directions(installation, monkeypatch):
    m,pkg,base,targets,peer=installation
    for root in (targets[1],targets[0]):
        m.select_candidate(root.name)
        result=m.activate_candidate()
        assert result['status']=='activated'
        assert peer.resolve()==(root / 'runtime/node_modules/@deepseek-ai').resolve()
        assert invoke(pkg,root,'verify').returncode==0


@pytest.mark.parametrize('damage', ['none','omit_declaration','extra_file','missing_base','missing_manifest','wrong_base','wrong_candidate','wrong_receipt'])
def test_actual_audit_requires_trusted_base_and_complete_diff(installation, monkeypatch, damage):
    m,pkg,base,targets,peer=installation
    root=targets[0]
    m.select_candidate(root.name)
    staged=root / 'home/profiles/node_modules/@code2paper/dsh-bundle/lib'
    staged.mkdir(parents=True)
    m.write_json(staged / 'build-receipt.json',{'frozen_runtime':{'runtime_tree_sha256':m.read_json(root/'manifest.json')['runtime_tree_sha256']}})
    m.write_json(root/'staging.json',{})
    monkeypatch.setattr(m,'verify_staging',lambda:{'tree_sha256':'fixture-stage'})
    obj=m.read_json(root/'manifest.json')
    if damage=='omit_declaration': obj['loop_origin_patch']['touched']=obj['loop_origin_patch']['touched'][:-1]
    elif damage=='extra_file':
        (root/'runtime/extra').write_text('extra');obj['runtime_tree_sha256']=m.tree_digest(m.inventory(root/'runtime'))
    elif damage=='missing_base': shutil.rmtree(base/'runtime')
    elif damage=='missing_manifest': (base/'manifest.json').unlink()
    elif damage=='wrong_base':
        (base/'runtime/package-lock.json').write_text('wrong')
        bm=m.read_json(base/'manifest.json');bm['runtime_tree_sha256']=m.tree_digest(m.inventory(base/'runtime'));m.write_json(base/'manifest.json',bm)
    elif damage=='wrong_candidate': obj['base_runtime_tree_sha256']='wrong'
    elif damage=='wrong_receipt': m.write_json(staged/'build-receipt.json',{'frozen_runtime':{'runtime_tree_sha256':'wrong'}})
    m.write_json(root/'manifest.json',obj)
    before=(root/'manifest.json').read_bytes()
    if damage=='none': assert m.audit_candidate_delivery()['status']=='PASS'
    else:
        with pytest.raises(RuntimeError): m.audit_candidate_delivery()
    assert before==(root/'manifest.json').read_bytes()


@pytest.mark.parametrize('damage',['none','missing_fifth','extra_file','wrong_base'])
def test_actual_setup_checks_base_and_generated_diff(installation,monkeypatch,damage):
    m,pkg,base,targets,peer=installation
    root=targets[0];shutil.rmtree(root)
    m.select_candidate(root.name,allow_missing=True)
    patch=pkg/'fixture_patch.py'
    touched=m.LOOP_ORIGIN_TOUCHED[:]
    if damage=='missing_fifth': touched=touched[:-1]
    if damage=='extra_file': touched=touched+['extra']
    patch.write_text('from pathlib import Path\nimport sys\nr=Path(sys.argv[1])\nfor rel in '+repr(touched)+':\n p=r/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text("patched\\n")\n')
    m.LOOP_ORIGIN_PATCH=patch
    def provision():
        obj=m.read_json(base/'manifest.json');obj['runtime_tree_sha256']=m.tree_digest(m.inventory(m.RUNTIME));m.write_json(root/'manifest.json',obj)
        return {'runtime_tree_sha256':obj['runtime_tree_sha256'],'profiles':{}}
    monkeypatch.setattr(m,'provision_candidate',provision)
    if damage=='wrong_base':
        (base/'runtime/package-lock.json').write_text('wrong')
    if damage=='none': assert m.loop_origin_setup()['candidate']==root.name
    else:
        with pytest.raises(RuntimeError): m.loop_origin_setup()
        assert not (root/'manifest.json').exists()
