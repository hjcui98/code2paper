/** R03 real DSH subprocess + real worker. UNIT projection, not V01 wire. */
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync, mkdirSync, symlinkSync } from 'node:fs';
import path from 'node:path';
import { after, before, test } from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { boot, loadOverlayPatches, loadProfileDirectory } from '@deepseek-ai/dsh-app-boot';
import { provideCmdline } from '@deepseek-ai/dsh-cmdline';
import type { Context } from '@deepseek-ai/cordis';
import type * as KernelApi from '../src/kernel-client.js';
import type { JsonObject } from '../src/wire.js';

const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
const pkg=path.join(repo,'integrations/dsh');
const devRoot=process.env.C2P_DSH_DEV_ROOT!;
const runtime=path.join(devRoot,'runtime');
const staged=path.join(devRoot,'home/profiles/node_modules/@code2paper/dsh-bundle');
const python=path.join(devRoot,'pyworker/bin/python');
let ctx: Context;
let root: string;
let api: typeof KernelApi;
let material: {bootstrap:string;initialize:JsonObject;scope:JsonObject;prepare:JsonObject};

before(async()=>{
  root=mkdtempSync(path.join(process.env.C2P_DSH_RUN_ROOT!,'stage04-subprocess-'));
  mkdirSync(path.join(root,'node_modules/@code2paper'),{recursive:true});
  symlinkSync(path.join(runtime,'node_modules/@deepseek-ai'),path.join(root,'node_modules/@deepseek-ai'),'dir');
  symlinkSync(staged,path.join(root,'node_modules/@code2paper/dsh-bundle'),'dir');
  const profileDir=path.join(devRoot,'home/profiles/code2paper-dev-compat');
  const profile=loadProfileDirectory('stage04-host-test',profileDir,path.join(runtime,'node_modules/@deepseek-ai/dsh/package.json'));
  const config=path.join(root,'cordis.yml'); writeFileSync(config,readFileSync(path.join(profileDir,'cordis.yml')));
  const overlay=path.join(root,'overlay.yml');
  writeFileSync(overlay,JSON.stringify([{id:'web-runtime',config:{printUrl:false,openBrowser:false,surfaceContext:false,trustedHosts:[]}}]));
  ctx=await boot('stage04-host-test',config,[...profile.layers.flatMap(layer=>layer.patches),...profile.patches,
    ...loadOverlayPatches('stage04-host-test',path.join(pkg,'dev/offline.patch.yml')),
    ...loadOverlayPatches('stage04-host-test',overlay)],host=>{
      provideCmdline(host,{args:['--host','127.0.0.1','--port','0','--no-open'],exit:()=>{}});
    });
  api=await import(pathToFileURL(path.join(staged,'lib/kernel-client.js')).href) as typeof KernelApi;
  const code=`import sys,json
from pathlib import Path
from dataclasses import asdict
from code2paper.agentic.authoring_execution_identity import CompositionSpecV1,_COMPOSITION_FILES,_COMPOSITION_TREES
from tests.integrations.dsh.stage04_support import durable_material
from code2paper.integrations.dsh.worker import rpc_schema_digest
from code2paper.integrations.dsh.protocol import MAX_FRAME_BYTES
p=Path(sys.argv[1]); files={}; trees={}
for name in _COMPOSITION_FILES:
 f=p/name; f.write_bytes(('UNIT:'+name).encode()); files[name]=f
for name in _COMPOSITION_TREES:
 d=p/name; d.mkdir(); (d/'module.js').write_text('UNIT only'); trees[name]=d
spec=CompositionSpecV1(files=files,trees=trees,effective_config=dict(model='test-only',options={},worker_version='1',renderer_version='1',tokenizer_version='1',meter_version='1'))
facade,contract,frozen,projection,budget,bootstrap=durable_material(p,spec)
scope=asdict(facade.context.scope)
print(json.dumps(dict(bootstrap=str(bootstrap),scope=scope,initialize=dict(protocol_version='c2p-dsh/1',
schema_digest=rpc_schema_digest(),validator_digest=facade.composition['validator_digest'],max_frame_bytes=MAX_FRAME_BYTES),
prepare=dict(**scope,frozen_ref=frozen.model_dump(mode='json'),projection_ref=facade.store.put_json(projection).model_dump(mode='json'),cap=4096))))`;
  const produced=spawnSync(python,['-c',code,root],{cwd:repo,env:{...process.env,PYTHONPATH:path.join(repo,'src')},encoding:'utf8',maxBuffer:1<<20});
  assert.equal(produced.status,0,produced.stderr);
  material=JSON.parse(produced.stdout) as typeof material;
});

after(async()=>{await ctx?.fiber.dispose();});

test('actual managed worker prepares, persists claim, exits and resumes in a fresh subprocess',async()=>{
  const launch={pythonExecutable:python,engineRoot:repo,bootstrapPath:material.bootstrap};
  const first=api.startKernelWorker(ctx,launch);
  let claim: JsonObject;
  try {
    const handshake=await first.call('initialize',material.initialize) as JsonObject;
    assert.equal(handshake.scope_mode,'dsh-durable-claim/1');
    await first.call('task.prepare',material.prepare);
    claim=await first.call('task.claim',{...material.scope,owner:'host:actual-subprocess'}) as JsonObject;
    assert.equal(claim.claim_fence,1);
    await first.call('task.bind',{...material.scope,claim,child_id:'child:test',session_id:'session:test'});
    await assert.rejects(first.call('model.generate',material.scope),/kernel_method_unavailable/);
  } finally { await first.close(); }
  const restarted=api.startKernelWorker(ctx,launch);
  try {
    await restarted.call('initialize',material.initialize);
    const resumed=await restarted.call('task.resume',{...material.scope,claim}) as JsonObject;
    assert.equal(resumed.state,'claimed');
    assert.deepEqual(resumed.binding,{child_id:'child:test',session_id:'session:test'});
    await restarted.call('task.cancel',{...material.scope,claim});
    const state=await restarted.call('task.read',material.scope) as JsonObject;
    assert.equal(state.state,'cancelled');
    writeFileSync(path.join(root,'result.json'),JSON.stringify({schema_version:'Stage04SubprocessTestV1',
      actual_service:true,fresh_process_resume:true,projection:'UNIT',state:'cancelled'}));
  } finally {await restarted.close();}
});
