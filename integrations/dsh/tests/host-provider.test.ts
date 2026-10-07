/** Stage A actual Loader/DSH subprocess/worker/pi-ai/HTTP/Session/publication. */
import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { setTimeout as delay } from 'node:timers/promises';
import { createServer } from 'node:http';
import type { Server } from 'node:http';
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, symlinkSync, unlinkSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { after, before, test } from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { boot, loadOverlayPatches, loadProfileDirectory } from '@deepseek-ai/dsh-app-boot';
import { provideCmdline } from '@deepseek-ai/dsh-cmdline';
import LlmRuntime, { createUserMessage } from '@deepseek-ai/dsh-llm';
import type { GenerateOptions } from '@deepseek-ai/dsh-llm';
import { Context, Service } from '@deepseek-ai/cordis';
import type { SessionId } from '@deepseek-ai/dsh-session';
import type {} from '@deepseek-ai/dsh-session-persistence';
import * as PiAi from '@deepseek-ai/dsh-llm-pi-ai';
import type * as KernelApi from '../src/kernel-client.js';
import type * as DriverApi from '../src/workflow-driver.js';
import type * as WriterApi from '../src/writer-request.js';
import type { JsonObject, JsonValue } from '../src/wire.js';
import type { GatedAdapterSource } from '../src/request-accounting.js';

const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
const pkg=path.join(repo,'integrations/dsh');
const devRoot=process.env.C2P_DSH_DEV_ROOT!;
const runtime=path.join(devRoot,'runtime');
const staged=path.join(devRoot,'home/profiles/node_modules/@code2paper/dsh-bundle');
const python=path.join(devRoot,'pyworker/bin/python');
const PY_IMPORTS=`from code2paper.agentic.digest import canonical_json_bytes,digest_json
from code2paper.integrations.dsh.protocol import strict_json_loads
from code2paper.integrations.dsh.writer_contract import seal_projection
from code2paper.agentic.unified_context_compiler import measure_unified_tokens
from code2paper.agentic.unified_context_models import conservative_token_meter
import sys`;
function py(code:string,input:unknown):string {
  const result=spawnSync(python,['-c',code],{cwd:repo,env:{...process.env,PYTHONPATH:path.join(repo,'src'),PYTHONDONTWRITEBYTECODE:'1'},
    input:JSON.stringify(input),encoding:'utf8',maxBuffer:2<<20});
  assert.equal(result.status,0,result.stderr); return result.stdout.trim();
}
function digest(value:unknown):string{return py(`${PY_IMPORTS}\nprint(digest_json(strict_json_loads(sys.stdin.buffer.read())))`,value);}

let ctx: Context;
let root: string;
let server: Server;
let kernel: KernelApi.KernelClient;
let restartKernel: () => KernelApi.KernelClient;
let driver: typeof DriverApi;
let writer: typeof WriterApi;
let native: GatedAdapterSource;
let descriptor: {bootstrap:string;scope:JsonObject;frozen_ref:JsonObject;input:WriterApi.WriterInputRefV1;
  budget_ref:JsonObject;composition_digest:string;tokenizer_digest:string;initialize:JsonObject};
let projection: WriterApi.WriterWireProjectionV1;
let contractRef: JsonObject;
const arrivals:{body:string;sse:string}[]=[];
const loopRequests: GenerateOptions[]=[];
const recoveryCut=process.env['C2P_STAGE04_TEST_RECOVERY_CUT'] ?? 'receipt';
assert.ok(['receipt','before-record','after-record','after-ingest'].includes(recoveryCut));
const outcome=process.env['C2P_STAGE04_TEST_OUTCOME'] ?? 'blocked';
const multistep=process.env['C2P_STAGE04_MULTISTEP'] === '1';
const compaction=process.env['C2P_STAGE04_COMPACTION'] === '1';
const deniedCompaction=process.env['C2P_STAGE04_COMPACTION_UNDECLARED'] === '1';
let auxiliaryNative:GatedAdapterSource;
let auxiliaryContext:Context|undefined;
class AuxiliaryCredentials extends Service {
  constructor(ctx:Context){super(ctx,'credentials');}
  async resolve(){return {value:'local-fake-service'};}
  async listRecords(){return [];}
}
let auxiliaryProviderConfig:JsonObject;
const nativeToolChoice=process.env['C2P_STAGE04_TEST_NATIVE_TOOL_CHOICE'] === '1';
// Private operator preparation mode only. Normal registered suites never wait
// for an external receipt, and preparation does not start the task epoch.
const operatorMode=process.env['C2P_STAGE04_TEST_OPERATOR_PACKAGE'] === '1';
const coverageReceipt=process.env['C2P_STAGE04_TEST_COVERAGE_RECEIPT'];
const normalMode=coverageReceipt !== undefined;
assert.ok(!(operatorMode && normalMode));
const executableMode=operatorMode || normalMode;
let providerConfig:JsonObject;
let frozenEndpoint:string|undefined;
let operatorLaunch:string;
let operatorReceipt:string;
let operatorCoreReceipt:string;
let operatorPreAdmissionMs:number;
let workerLauncher:string;
const pageKind=process.env['C2P_STAGE04_TEST_PAGE_KIND'] ?? 'technical';
const nativeFinish=process.env['C2P_STAGE04_NATIVE_TOOL_FINISH'] ?? 'tool_calls';
assert.ok(['tool_calls','stop'].includes(nativeFinish));
assert.ok(['technical','author'].includes(pageKind));
assert.ok(['blocked','draft','research_required','invalid_content','wrong_formula_binding','wrong_atom_binding',
  'inline_formula','formula_metadata','missing_witness','packet10_original','text_stop','unknown_tool','provider_error','provider_error_cached_usage',
  'finish_without_usage','usage_without_finish','disconnect','timeout',
  'cap_drift','composition_drift','budget_exhausted','raw_missing','raw_corrupt','unicode','cancel'].includes(outcome));
let cancelFormal: (() => void) | undefined;
let providerUnfinished=false;
const transportDeadline=new AbortController();
const unicodeReason='缺证据：边界🙂𝄞，组合 e\u0301 与换行\n保持原始内容';
let responseRaw=JSON.stringify({schema_version:'WriterTaskResultV1',result:{outcome:'blocked',reason:'controlled offline refusal',recovery_action:'new scoped task'}});
if (outcome === 'unicode') responseRaw=JSON.stringify({schema_version:'WriterTaskResultV1',result:{outcome:'blocked',
  reason:unicodeReason,recovery_action:'按原任务补证'}}).replace('🙂','\\ud83d\\ude42');
if (outcome === 'packet10_original') {
  const raw=readFileSync(path.join(repo,'tests/integrations/dsh/fixtures/packet10-rejected-terminal.json'));
  assert.equal(createHash('sha256').update(raw).digest('hex'),'335194b5e7ad149d022daada3110c35f15f0746ef26ed8a9d3e1667133c59c0c');
  responseRaw=raw.toString('utf8');
}

async function put(value:JsonValue):Promise<JsonObject> {
  return await putRaw(JSON.stringify(value));
}
async function putRaw(raw:string):Promise<JsonObject> {
  return await kernel.call('artifact.record',{...descriptor.scope,media_type:'application/json',
    raw_base64:Buffer.from(raw,'utf8').toString('base64')}) as JsonObject;
}

async function closedPythonSentinel():Promise<JsonObject> {
  // Readback starts a fresh worker. Its final observation must follow the
  // original close/exit proof, rather than retaining its installed snapshot.
  await kernel.close();
  const sentinel=JSON.parse(readFileSync(path.join(root,'python-sentinel.json'),'utf8')) as JsonObject;
  assert.equal(sentinel.schema_version,'PythonLlmRefusalSentinelV1');
  assert.equal(sentinel.state,'closed');assert.equal(sentinel.probe_refused,true);
  assert.equal(sentinel.model_calls,0);assert.equal(sentinel.network_calls,0);
  return sentinel;
}

before(async()=>{
  if (normalMode) {
    assert.ok(path.isAbsolute(coverageReceipt!));
    // This locator supplies only the offline server profile. The normal CLI
    // independently asks the original Python owner to validate the final
    // certificate and admit the fresh target before any task is prepared.
    const coverage=JSON.parse(readFileSync(coverageReceipt!,'utf8')) as {machine_plan:{operator:{launch_path:string}}};
    const qualified=JSON.parse(readFileSync(coverage.machine_plan.operator.launch_path,'utf8')) as {provider_config:JsonObject};
    providerConfig=qualified.provider_config;
    const providers=providerConfig.providers as JsonObject;
    const provider=providers.deepseek as JsonObject;
    assert.equal(typeof provider.baseURL,'string');frozenEndpoint=provider.baseURL as string;
    const url=new URL(frozenEndpoint);
    assert.equal(url.protocol,'http:');assert.equal(url.hostname,'127.0.0.1');
    assert.equal(url.username,'');assert.equal(url.password,'');assert.equal(url.search,'');assert.equal(url.hash,'');
    assert.ok(Number.isSafeInteger(Number(url.port)) && Number(url.port)>0 && Number(url.port)<=65535);
    assert.notEqual(Number(url.port),8006);
  }
  root=mkdtempSync(path.join(process.env.C2P_DSH_RUN_ROOT!,'stage04-provider-'));
  console.log(`STAGE04_PROVIDER_ROOT=${root}`);
  mkdirSync(path.join(root,'node_modules/@code2paper'),{recursive:true});
  symlinkSync(path.join(runtime,'node_modules/@deepseek-ai'),path.join(root,'node_modules/@deepseek-ai'),'dir');
  symlinkSync(staged,path.join(root,'node_modules/@code2paper/dsh-bundle'),'dir');
  const profileDir=path.join(devRoot,'home/profiles/code2paper-dev-compat');
  const profile=loadProfileDirectory('stage04-provider-test',profileDir,path.join(runtime,'node_modules/@deepseek-ai/dsh/package.json'));
  const config=path.join(root,'cordis.yml'); writeFileSync(config,readFileSync(path.join(profileDir,'cordis.yml')));
  const overlay=path.join(root,'overlay.yml');
  writeFileSync(overlay,JSON.stringify([{id:'web-runtime',config:{printUrl:false,openBrowser:false,surfaceContext:false,trustedHosts:[]}},
    {id:'session-persistence-jsonl',config:{root:path.join(root,'sessions'),compression:'none'}}]));
  ctx=await boot('stage04-provider-test',config,[...profile.layers.flatMap(layer=>layer.patches),...profile.patches,
    ...loadOverlayPatches('stage04-provider-test',path.join(pkg,'dev/offline.patch.yml')),
    ...loadOverlayPatches('stage04-provider-test',overlay)],host=>{
      provideCmdline(host,{args:['--host','127.0.0.1','--port','0','--no-open'],exit:()=>{}});
      host.on('llm/stream',(request,next)=>{loopRequests.push(request);return next();});
      host.on('agent/request',async(_request,next)=>{
        const config=await next();
        return outcome === 'cap_drift' && arrivals.length === 1 ? {...config,maxTokens:4095} : config;
      });
    });
  const kernelApi=await import(pathToFileURL(path.join(staged,'lib/kernel-client.js')).href) as typeof KernelApi;
  driver=await import(pathToFileURL(path.join(staged,'lib/workflow-driver.js')).href) as typeof DriverApi;
  writer=await import(pathToFileURL(path.join(staged,'lib/writer-request.js')).href) as typeof WriterApi;
  server=createServer((request,response)=>{
    let body='';request.setEncoding('utf8');request.on('data',(chunk:string)=>{body+=chunk;});
    request.on('end',()=>{
      if (nativeToolChoice) assert.deepEqual(JSON.parse(body).tool_choice,
        {type:'function',function:{name:'c2p_terminal'}});
      if (outcome === 'cancel' && arrivals.length === 1) {
        arrivals.push({body,sse:''});providerUnfinished=true;
        assert.ok(cancelFormal !== undefined,'formal cancellation must be armed before transport');
        cancelFormal();
        // The fake provider remains listening/unfinished until its own owner
        // closes it. Client abort, DSH idle and worker exit are no exit proof.
        return;
      }
      const id=`stage04-http-${String(arrivals.length)}`;
      if (compaction && arrivals.length===2) {
        const wire=JSON.parse(body) as JsonObject;
        assert.ok(wire.tools===undefined || Array.isArray(wire.tools) && wire.tools.length===0);
        assert.ok(wire.tool_choice===undefined || wire.tool_choice==='none');
        const frames=[{choices:[{index:0,delta:{role:'assistant',content:'Derived summary only: continue the pending Writer task.'},finish_reason:null}]},
          {choices:[{index:0,delta:{},finish_reason:'stop'}],usage:{prompt_tokens:17,completion_tokens:11}}];
        const sse=frames.map(frame=>`data: ${JSON.stringify(frame)}\n\n`).join('')+'data: [DONE]\n\n';
        arrivals.push({body,sse});response.writeHead(200,{'content-type':'text/event-stream'});response.end(sse);return;
      }
      if (multistep && arrivals.length === 1) {
        const parsed=JSON.parse(body) as {messages:{content:unknown}[]};
        const texts=parsed.messages.flatMap(message=>typeof message.content === 'string' ? [message.content] : []);
        let grant:string|undefined;
        for (const text of texts) {try {const value=JSON.parse(text) as {navigation_grants?:{grant_id:string}[]};
          grant ??= value.navigation_grants?.[0]?.grant_id;}catch{}}
        assert.ok(grant,'first navigation uses only the actually issued public opaque grant');
        const frames=[{choices:[{index:0,delta:{role:'assistant',tool_calls:[{index:0,id,type:'function',
          function:{name:'c2p_read',arguments:JSON.stringify({grant_id:grant,offset:0,length:1})}}]},finish_reason:null}]},
          {choices:[{index:0,delta:{},finish_reason:'tool_calls'}],usage:{prompt_tokens:17,completion_tokens:11}}];
        const sse=frames.map(frame=>`data: ${JSON.stringify(frame)}\n\n`).join('')+'data: [DONE]\n\n';
        arrivals.push({body,sse});response.writeHead(200,{'content-type':'text/event-stream'});response.end(sse);return;
      }
      const split=outcome === 'unicode' ? responseRaw.indexOf('\\ud83d')+3 : responseRaw.length;
      const parts=outcome === 'unicode' ? [responseRaw.slice(0,split),responseRaw.slice(split)] : [responseRaw];
      const events=['provider_error','provider_error_cached_usage'].includes(outcome) && arrivals.length === 1 ? [
        {choices:[{index:0,delta:{role:'assistant',reasoning:'The request is being processed.'},finish_reason:null}]},
        ...(outcome === 'provider_error_cached_usage' ? [{choices:[],usage:{prompt_tokens:0,completion_tokens:3,total_tokens:3}}] : []),
        {error:{message:'Controlled provider stream failure',type:'InternalServerError',code:500}}]
        : outcome === 'unknown_tool' && arrivals.length === 1 ? [
        {choices:[{index:0,delta:{role:'assistant',tool_calls:[{index:0,id,type:'function',
          function:{name:'"c2p_terminal"\n<parameter',arguments:'{}'}}]},finish_reason:null}]},
        {choices:[{index:0,delta:{},finish_reason:'tool_calls'}],usage:{prompt_tokens:17,completion_tokens:11}}]
        : outcome === 'text_stop' && arrivals.length === 1 ? [
        {choices:[{index:0,delta:{role:'assistant',content:'```json\n'+responseRaw+'\n```'},finish_reason:null}]},
        {choices:[{index:0,delta:{},finish_reason:'stop'}],usage:{prompt_tokens:17,completion_tokens:11}}]
        : [...parts.map((argumentsPart,index)=>({choices:[{index:0,delta:{...(index === 0 ? {role:'assistant'} : {}),
        tool_calls:[{index:0,...(index === 0 ? {id,type:'function'} : {}),
          function:{...(index === 0 ? {name:'c2p_terminal'} : {}),arguments:argumentsPart}}]},finish_reason:null}]})),
        {choices:[{index:0,delta:{},finish_reason:nativeFinish}],usage:{prompt_tokens:17,completion_tokens:11}}];
      const sse=`${events.map(event=>`data: ${JSON.stringify(event)}\n\n`).join('')}data: [DONE]\n\n`;
      if (['finish_without_usage','usage_without_finish','disconnect','timeout'].includes(outcome) && arrivals.length===1) {
        const partial={choices:[{index:0,delta:{role:'assistant',reasoning:'Partial response'},finish_reason:null}]};
        const usage={choices:[],usage:{prompt_tokens:17,completion_tokens:3,total_tokens:20}};
        const frames=outcome==='finish_without_usage'
          ? [partial,{choices:[{index:0,delta:{},finish_reason:'stop'}]}]
          : outcome==='usage_without_finish' ? [partial,usage] : [partial];
        const raw=frames.map(event=>`data: ${JSON.stringify(event)}\n\n`).join('');
        const complete=['finish_without_usage','usage_without_finish'].includes(outcome);
        arrivals.push({body,sse:raw+(complete ? 'data: [DONE]\n\n' : '')});
        response.writeHead(200,{'content-type':'text/event-stream'});response.write(raw);
        if (complete) response.end('data: [DONE]\n\n');
        else if (outcome==='disconnect') setTimeout(()=>response.destroy(),50);
        else {providerUnfinished=true;setTimeout(()=>transportDeadline.abort(new DOMException('Controlled request timeout','TimeoutError')),100);}
        return;
      }
      arrivals.push({body,sse});response.writeHead(200,{'content-type':'text/event-stream'});
      if (outcome === 'unicode') {
        // A real HTTP write splits the UTF-8 encoding inside a Chinese code
        // point, independently of the raw tool JSON split inside an ASCII
        // surrogate escape. Each delta string remains valid Unicode itself.
        const bytes=Buffer.from(sse);const boundary=bytes.indexOf(Buffer.from('缺'))+1;
        assert.ok(boundary > 0);response.write(bytes.subarray(0,boundary));
        setImmediate(()=>response.end(bytes.subarray(boundary)));
      } else response.end(sse);
    });
  });
  await new Promise<void>(resolve=>server.listen(frozenEndpoint === undefined ? 0 : Number(new URL(frozenEndpoint).port),'127.0.0.1',resolve));
  const address=server.address();assert.ok(address !== null && typeof address !== 'string');
  const endpoint=frozenEndpoint ?? `http://127.0.0.1:${String(address.port)}`;
  providerConfig ??= {providers:{deepseek:{apiKeyEnv:'C2P_STAGE04_TEST_ONLY_KEY',baseURL:endpoint,
    reasoning:'off',retryPolicy:{mode:'normal',maxRetries:0}}}};
  if (multistep) {
    assert.ok(!executableMode);
    const profile=(providerConfig.providers as JsonObject).deepseek as JsonObject;
    profile.toolChoice='required';
  }
  if (nativeToolChoice) {
    assert.ok(!executableMode,'tool choice fixture is a separately registered native scenario');
    (providerConfig.providers as JsonObject).deepseek = {
      ...((providerConfig.providers as JsonObject).deepseek as JsonObject),
      toolChoice:{type:'function',function:{name:'c2p_terminal'}},
    };
  }
  const guard=path.join(repo,'tests/integrations/dsh/fixtures/guarded_worker.py');
  const launcher=path.join(root,'python-worker-guard');
  workerLauncher=launcher;
  const quote=(value:string):string=>`'${value.replaceAll("'","'\\''")}'`;
  writeFileSync(launcher,`#!/bin/sh\nexec ${quote(python)} ${quote(guard)} ${quote(path.join(root,'python-sentinel.json'))} "$@"\n`);
  chmodSync(launcher,0o700);
  const files:Record<string,string>={loader:path.join(runtime,'node_modules/@deepseek-ai/cordis-plugin-loader/lib/index.js'),
    peer:path.join(pkg,'node_modules/@deepseek-ai/dsh-llm/package.json'),bundle_source:path.join(pkg,'src/index.ts'),bundle_lock:path.join(pkg,'package-lock.json'),
    build_input:path.join(pkg,'dev/toolchain/tsconfig.build.json'),bundle_js:path.join(staged,'lib/index.js'),build_receipt:path.join(staged,'lib/build-receipt.json'),
    stage:path.join(devRoot,'staging.json'),node:process.execPath,preset:path.join(staged,'presets/code2paper.patch.yml'),persona:path.join(staged,'lib/task-tools.js'),
    tool_schema:path.join(pkg,'wire-v1/native-terminal.schema.json'),renderer:path.join(staged,'lib/writer-request.js'),
    python_executable:python,python_environment:path.join(devRoot,'pyworker/pyvenv.cfg'),
    python_dependencies:path.join(pkg,'dev/pyworker-requirements.lock'),worker:path.join(repo,'src/code2paper/integrations/dsh/worker.py'),
    tokenizer:path.join(repo,'src/code2paper/agentic/unified_context_models.py'),meter:path.join(repo,'src/code2paper/agentic/unified_context_compiler.py'),
    test_worker_launcher:launcher,test_worker_refusal_sentinel:guard,
    host_config:config,host_overlay:overlay,host_profile:path.join(profileDir,'cordis.yml'),
    host_profile_package:path.join(profileDir,'package.json'),host_profile_patch:path.join(profileDir,'cordis.patch.yml'),
    host_offline_policy:path.join(pkg,'dev/offline.patch.yml')};
  const trees={runtime:path.join(runtime,'node_modules'),dependencies:path.join(pkg,'node_modules'),python_runtime:path.join(devRoot,'pyworker/lib/python3.13/site-packages'),
    host_profile_runtime:profileDir,staged_bundle:staged};
  const produced=spawnSync(python,['-m','tests.integrations.dsh.fixtures.stage04_host_material'],{cwd:repo,
    env:{...process.env,PYTHONPATH:path.join(repo,'src'),PYTHONDONTWRITEBYTECODE:'1'},
    input:JSON.stringify({root,files,trees,endpoint,fixture_mode:normalMode ? 'normal' : 'qualification',page_kind:pageKind,zero_writer_budget:outcome === 'budget_exhausted',multistep,compaction:compaction && !deniedCompaction,
      ...(multistep ? {native_tool_choice:'required'} : {}),
      ...(nativeToolChoice ? {native_tool_choice:{type:'function',function:{name:'c2p_terminal'}}} : {})}),encoding:'utf8',maxBuffer:2<<20});
  assert.equal(produced.status,0,produced.stderr); descriptor=JSON.parse(produced.stdout) as typeof descriptor;
  if (['draft','invalid_content','wrong_formula_binding','wrong_atom_binding','inline_formula','formula_metadata','missing_witness'].includes(outcome)) {
    const material=JSON.parse(produced.stdout) as {writer_raw:string};
    const draft=JSON.parse(material.writer_raw) as {section_markdown:string;paragraphs:{paragraph_markdown:string;
      used_formula_package_ids:string[];witnesses:{witness_kind:string;target_id:string;exact_text:string}[]}[]};
    if (outcome === 'invalid_content') {
      draft.section_markdown='An unrelated operation is performed.';
      draft.paragraphs[0]!.paragraph_markdown=draft.section_markdown;
    }
    if (outcome === 'wrong_formula_binding') {
      const paragraph=draft.paragraphs[0]!;
      const original=paragraph.used_formula_package_ids[0]!;
      const foreign='pkg:formula:outside-frozen-contract';
      assert.ok(original);assert.ok(draft.section_markdown.includes(`[[FORMULA:${original}]]`));
      draft.section_markdown=draft.section_markdown.replace(`[[FORMULA:${original}]]`,`[[FORMULA:${foreign}]]`);
      paragraph.paragraph_markdown=paragraph.paragraph_markdown.replace(`[[FORMULA:${original}]]`,`[[FORMULA:${foreign}]]`);
      paragraph.used_formula_package_ids=[foreign];
    }
    if (outcome === 'wrong_atom_binding') {
      const paragraph=draft.paragraphs[0]!;
      assert.ok(paragraph.witnesses[0]);
      paragraph.witnesses.push({witness_kind:'atom',target_id:'atom:outside-frozen-contract',
        exact_text:paragraph.witnesses[0]!.exact_text});
    }
    if (outcome === 'inline_formula' || outcome === 'formula_metadata') {
      const paragraph=draft.paragraphs[0]!;
      const original=paragraph.used_formula_package_ids[0]!;
      const replacement=outcome === 'inline_formula' ? '$$ output = factor * input $$' : `Formula package: ${original}`;
      paragraph.paragraph_markdown=paragraph.paragraph_markdown.replace(`[[FORMULA:${original}]]`,replacement);
      draft.section_markdown=draft.section_markdown.replace(`[[FORMULA:${original}]]`,replacement);
    }
    if (outcome === 'missing_witness') draft.paragraphs[0]!.witnesses=[];
    responseRaw=JSON.stringify({schema_version:'WriterTaskResultV1',result:{outcome:'draft',draft}});
  }
  if (outcome === 'research_required') responseRaw=(JSON.parse(produced.stdout) as {research_required_raw:string}).research_required_raw;
  restartKernel=()=>kernelApi.startKernelWorker(ctx,{pythonExecutable:launcher,engineRoot:repo,bootstrapPath:descriptor.bootstrap});
  kernel=restartKernel();
  await kernel.call('initialize',descriptor.initialize);
  // Obtain the actual public adapter registration; no private runtime reader.
  process.env['C2P_STAGE04_TEST_ONLY_KEY']='local-fake-service';
  const register=ctx.llm.registerAdapter.bind(ctx.llm);
  let registration: ReturnType<typeof register> | undefined;
  ctx.llm.registerAdapter=(providers,adapter)=>{native=adapter as unknown as GatedAdapterSource;registration=register(providers,adapter);return registration;};
  try {await ctx.plugin(PiAi,providerConfig as never);} finally {ctx.llm.registerAdapter=register;}
  assert.ok(registration !== undefined);
  if (compaction) {
    auxiliaryProviderConfig=JSON.parse(JSON.stringify(providerConfig)) as JsonObject;
    const profile=(auxiliaryProviderConfig.providers as JsonObject).deepseek as JsonObject;
    delete profile.toolChoice;
    auxiliaryContext=new Context();new LlmRuntime(auxiliaryContext);new AuxiliaryCredentials(auxiliaryContext);
    const auxiliaryRegister=auxiliaryContext.llm.registerAdapter.bind(auxiliaryContext.llm);let dispose:ReturnType<typeof auxiliaryRegister>|undefined;
    auxiliaryContext.llm.registerAdapter=(providers,adapter)=>{auxiliaryNative=adapter as unknown as GatedAdapterSource;
      dispose=auxiliaryRegister(providers,adapter);return dispose;};
    try {await auxiliaryContext.plugin(PiAi,auxiliaryProviderConfig as never);} finally {auxiliaryContext.llm.registerAdapter=auxiliaryRegister;}
    assert.ok(dispose);dispose();
  }
  // A separately counted offline C00 calibration supplies real loop/provider bytes.
  const calibrator=await ctx.agents.create({sessionId:'stage04-calibrator' as SessionId,
    setup:agentCtx=>{writer.installNativeWriter(agentCtx,descriptor.input);agentCtx.on('agent/pre-step',(request,next)=>request.step > 1 ? Promise.resolve({kind:'reject'}) : next());}});
  let binding:JsonObject;
  try {
    binding=await writer.renderWriterInput(calibrator.agent,descriptor.input);
    calibrator.agent.followup(createUserMessage({content:[{type:'text',text:descriptor.input.task_view_json}],source:{kind:'user'}}));
    await calibrator.agent.whenIdle();await ctx.sessionPersistence.flush();
    assert.equal(arrivals.length,1);assert.equal(loopRequests.length,1);
  } finally {await calibrator.dispose();registration();}
  const loop=JSON.parse(JSON.stringify(loopRequests[0],(key,value:unknown)=>key === 'signal' ? undefined : value)) as JsonObject;
  const loopRef=await put(loop);const providerRef=await putRaw(arrivals[0]!.body);
  const comparison=await put({binding,loop_digest:loopRef.bytes_digest!,provider_digest:providerRef.bytes_digest!});
  const equivalence=await put({schema_version:'WriterWireEquivalenceV1',input_digest:descriptor.input.input_digest,
    renderer_digest:descriptor.input.renderer_digest,composition_digest:descriptor.composition_digest,projection_material_digest:digest(binding),
    loop_request_ref:loopRef,provider_wire_ref:providerRef,comparison_ref:comparison,
    transport_whitelist:['request.signal','request.sessionId','messages.id','messages.createdAt']});
  const measured=Number(py(`${PY_IMPORTS}\nprint(measure_unified_tokens(strict_json_loads(sys.stdin.buffer.read()),meter=conservative_token_meter()))`,arrivals[0]!.body));
  const measurement=await put({schema_version:'WriterMeasurementV1',input_digest:descriptor.input.input_digest,
    renderer_digest:descriptor.input.renderer_digest,tokenizer_digest:descriptor.tokenizer_digest,meter_version:'conservative_utf8_bytes_div_4',
    measured_input_tokens:measured,context_tokens:131072,safety_margin_tokens:512,thinking_tokens:0,post_clamp_max_output_tokens:4096,
    measured_wire_digest:providerRef.bytes_digest!});
  projection=JSON.parse(py(`${PY_IMPORTS}\nprint(canonical_json_bytes(seal_projection(strict_json_loads(sys.stdin.buffer.read()))).decode())`,
    {schema_version:'WriterWireProjectionV1',protocol_version:'c2p-dsh/1',...binding,renderer_version:descriptor.input.renderer_version,
      task_view_digest:digest(descriptor.input.writer_request.input_payload),terminal_schema_digest:digest(descriptor.input.terminal_schema),
      measurement_ref:measurement,wire_equivalence_ref:equivalence})) as WriterApi.WriterWireProjectionV1;
  const projectionRef=await put(projection);
  if (executableMode) {
    assert.equal(outcome,'blocked');assert.equal(recoveryCut,'receipt');
    operatorLaunch=path.join(root,'operator-launch.json');operatorReceipt=normalMode ? coverageReceipt! : path.join(root,'operator-offline-receipt.json');
    operatorCoreReceipt=path.join(root,'operator-core-receipt.json');
    const raw=Buffer.from(JSON.stringify({schema_version:'DshSingleWriterLaunchV1',config_path:config,overlay_paths:[overlay],cwd:root,
      scope:descriptor.scope,run_id:'stage04-real',owner:'host:operator-cli',budget_ref:descriptor.budget_ref,
      frozen_ref:descriptor.frozen_ref,projection_ref:projectionRef,input:descriptor.input,projection,initialize:descriptor.initialize,
      provider_config:providerConfig}));
    writeFileSync(operatorLaunch,raw);
    await assert.rejects(kernel.call('task.read',descriptor.scope),/task_not_prepared/);
    operatorPreAdmissionMs=Date.now();
    const initialBudget=JSON.parse(py(`${PY_IMPORTS}\nfrom pathlib import Path\nfrom code2paper.agentic.unified_invocation_ledger import read_run_budget_state\nprint(canonical_json_bytes(read_run_budget_state(Path(strict_json_loads(sys.stdin.buffer.read())))).decode())`,
      path.join(root,'run/artifacts/06_authoring/invocations'))) as JsonObject;
    assert.equal(initialBudget.call_count,0);assert.equal(initialBudget.spent_input_tokens,0);assert.equal(initialBudget.pending_input_tokens,0);
    await kernel.close();
    const bootstrap=JSON.parse(readFileSync(descriptor.bootstrap,'utf8')) as JsonObject;
    bootstrap.host_launch_binding={schema_version:'DshHostLaunchBindingV1',path:operatorLaunch,
      bytes_digest:`sha256:${createHash('sha256').update(raw).digest('hex')}`,byte_length:raw.length};
    writeFileSync(descriptor.bootstrap,JSON.stringify(bootstrap));
    writeFileSync(path.join(root,'operator-ready.json'),JSON.stringify({schema_version:'Stage04OperatorPreparationV1',
      bootstrap:descriptor.bootstrap,launch:operatorLaunch,receipt:operatorReceipt,core_receipt:operatorCoreReceipt,task_root:root,
      candidate:process.env.C2P_DSH_CANDIDATE,task_prepared:false,calibration_sends:1,original_budget_state:initialBudget,
      task_not_prepared_observed_ms:operatorPreAdmissionMs}));
    console.log(`STAGE04_OPERATOR_READY=${path.join(root,'operator-ready.json')}`);
    return;
  }
  contractRef=await kernel.call('task.prepare',{...descriptor.scope,frozen_ref:descriptor.frozen_ref,projection_ref:projectionRef,cap:4096}) as JsonObject;
});

after(async()=>{
  const failures:unknown[]=[];
  const address=server?.address();
  for (const cleanup of [()=>kernel?.close(),()=>auxiliaryContext?.fiber.dispose(),()=>ctx?.sessionPersistence.flush(),()=>ctx?.fiber.dispose(),async()=>{
    if (server !== undefined) {server.closeAllConnections();await new Promise<void>((resolve,reject)=>server.close(error=>error ? reject(error) : resolve()));}
  }]) {try {await cleanup();} catch(error) {failures.push(error);}}
  delete process.env['C2P_STAGE04_TEST_ONLY_KEY'];
  if (address !== null && address !== undefined && typeof address !== 'string') {
    const probe=createServer();
    await new Promise<void>((resolve,reject)=>{probe.once('error',reject);probe.listen(address.port,'127.0.0.1',resolve);});
    await new Promise<void>((resolve,reject)=>probe.close(error=>error ? reject(error) : resolve()));
  }
  if (root !== undefined) writeFileSync(path.join(root,'cleanup.json'),JSON.stringify({worker_scope_quiescent:failures.length === 0,
    provider_is_offline_fake:true,provider_port_rebound:address !== null && address !== undefined,
    sentinel:existsSync(path.join(root,'python-sentinel.json')) ? JSON.parse(readFileSync(path.join(root,'python-sentinel.json'),'utf8')) : null}));
  if (failures.length) throw new AggregateError(failures,'stage04_cleanup_failed');
});

test(`actual bound Writer ${pageKind} ${outcome}${multistep ? ' with multistep' : ''}${compaction ? ' with forced compaction' : ''}${deniedCompaction ? ' with undeclared auxiliary budget' : ''} and new-process recovery at ${recoveryCut}${nativeFinish === 'stop' ? ' with native stop' : ''}${nativeToolChoice ? ' with named native tool selection' : ''}${process.env['C2P_STAGE04_RELEASE_FAULT'] === '1' ? ' with backend release failure' : ''}`,async()=>{
  if (nativeToolChoice) {
    // Calibration has consumed the original provider path. Selection must be
    // observed in its actual wire, rather than inferred from our config.
    assert.equal(arrivals.length,1);
    assert.deepEqual(JSON.parse(arrivals[0]!.body).tool_choice,
      {type:'function',function:{name:'c2p_terminal'}});
  }
  if (executableMode) {
    const deadline=Date.now()+4_800_000;
    while (operatorMode && !existsSync(operatorCoreReceipt)) {
      if (Date.now()>=deadline) throw new Error('test_operator_receipt_wait_expired');
      await delay(250);
    }
    // Keep the fixture server responsive while the actual executable starts
    // its own Loader and private worker in this existing offline namespace.
    // This exercises process.argv and the OS exit code, not a function replay.
    const executable=path.join(staged,'lib/cli.js');
    const argv=[executable,normalMode ? 'run' : 'qualify','--experimental-dsh','--candidate',process.env.C2P_DSH_CANDIDATE!,
      '--python',workerLauncher,'--engine-root',repo,'--bootstrap',descriptor.bootstrap,
      '--offline-receipt',normalMode ? coverageReceipt! : operatorCoreReceipt,'--launch-file',operatorLaunch];
    const child=spawn(process.execPath,argv,{cwd:repo,env:{...process.env},stdio:['ignore','pipe','pipe']});
    let stdout='';let stderr='';
    let exitCode:number|null=null;
    const timer=setTimeout(()=>child.kill('SIGTERM'),360_000);
    try {
      child.stdout.setEncoding('utf8');child.stderr.setEncoding('utf8');
      child.stdout.on('data',(data:string)=>{stdout+=data;});
      child.stderr.on('data',(data:string)=>{stderr+=data;});
      const ended=await new Promise<{code:number|null;signal:NodeJS.Signals|null}>((resolve,reject)=>{
        child.once('error',reject);child.once('close',(code,signal)=>resolve({code,signal}));
      });
      writeFileSync(path.join(root,'operator-cli-output.log'),stdout);
      writeFileSync(path.join(root,'operator-cli-error.log'),stderr);
      assert.equal(ended.signal,null,'actual CLI must finish without a termination signal');
      assert.equal(ended.code,0,stdout);exitCode=ended.code;
    } finally {clearTimeout(timer);}

    const resultLine=stdout.trim().split('\n').at(-1)!;
    const qualification=JSON.parse(resultLine) as JsonObject;
    let admission:JsonObject|undefined;
    if (normalMode) {
      assert.equal(qualification.schema_version,'DshHostExecutionResultV1');
      admission=qualification.admission as JsonObject;
      assert.equal(admission.schema_version,'DshTargetAdmissionV1');assert.equal(admission.admitted,true);
      assert.equal(admission.scope,'dsh-stage04-offline');assert.equal(admission.qualification_only,false);
      assert.equal(admission.normal_entry_authorized,true);assert.equal(admission.model_execution_authorized,false);
      assert.equal(admission.parallel_agents,false);assert.deepEqual(admission.target_scope,descriptor.scope);
      assert.equal(admission.coverage_receipt_digest,`sha256:${createHash('sha256').update(readFileSync(coverageReceipt!)).digest('hex')}`);
      assert.equal(admission.receipt_digest,admission.coverage_receipt_digest);
      assert.equal(admission.composition_digest,descriptor.composition_digest);
    } else {
      assert.equal(qualification.schema_version,'DshHostQualificationResultV1');
      assert.equal(qualification.admission_scope,'dsh-stage04-qualification');
      assert.equal(qualification.qualification_only,true);assert.equal(qualification.normal_entry_authorized,false);
      assert.equal(qualification.model_execution_authorized,false);
    }
    kernel=restartKernel();await kernel.call('initialize',descriptor.initialize);
    const state=await kernel.call('task.read',descriptor.scope) as JsonObject;
    assert.equal(state.state,'terminal');assert.ok(state.receipt !== null);
    assert.equal((state.receipt as JsonObject).domain_status,'blocked');assert.equal(arrivals.length,2);
    assert.deepEqual(qualification.receipt,state.receipt);
    assert.ok(typeof qualification.admission_completed_ms === 'number' && qualification.admission_completed_ms>=operatorPreAdmissionMs);
    assert.ok(typeof state.epoch_started_ms === 'number' && state.epoch_started_ms>=qualification.admission_completed_ms);
    const budget=JSON.parse(py(`${PY_IMPORTS}\nfrom pathlib import Path\nfrom code2paper.agentic.unified_invocation_ledger import read_run_budget_state\nprint(canonical_json_bytes(read_run_budget_state(Path(strict_json_loads(sys.stdin.buffer.read())))).decode())`,
      path.join(root,'run/artifacts/06_authoring/invocations'))) as JsonObject;
    assert.equal(budget.call_count,1);assert.equal(budget.spent_input_tokens,17);assert.equal(budget.pending_input_tokens,0);
    writeFileSync(path.join(root,'provider-observations.json'),JSON.stringify(arrivals));
    const sentinel=await closedPythonSentinel();
    const actualNetworkNamespace=JSON.parse(py(`${PY_IMPORTS}\nfrom code2paper.integrations.dsh.qualification import network_namespace_identity\nprint(canonical_json_bytes(network_namespace_identity()).decode())`,null)) as JsonObject;
    if (normalMode) assert.deepEqual(admission!.network_namespace,actualNetworkNamespace);
    writeFileSync(path.join(root,'operator-result.json'),JSON.stringify({schema_version:'Stage04OperatorResultV1',
      actual_cli_executable:true,executable,argv,cwd:repo,exit_code:exitCode,actual_network_namespace:actualNetworkNamespace,admission_scope:normalMode ? admission!.scope : qualification.admission_scope,
      ...(normalMode ? {normal_cli_result:qualification,target_admission:admission,coverage_receipt:coverageReceipt} : {}),
      receipt:state.receipt,original_budget_state:budget,sentinel,calibration_sends:1,task_sends:1,task_epoch_started_after_admission:true,
      task_epoch_started_ms:state.epoch_started_ms,admission_completed_ms:qualification.admission_completed_ms,
      task_not_prepared_observed_ms:operatorPreAdmissionMs}));
    return;
  }
  const authority=new driver.KernelAuthority(kernel,{scope:descriptor.scope as unknown as DriverApi.KernelTaskScope,
    caller:{executionId:String(descriptor.scope.execution_id),runId:'stage04-real',hostGeneration:1},owner:'host:stage04-real',
    compositionDigest:descriptor.composition_digest,contractRef,budgetRef:descriptor.budget_ref,
    ...(multistep ? {accountingVersion:'c2p-dsh-task-loop-v2' as const,providerConfig} : {})});
  const call=kernel.call.bind(kernel);
  const releaseFault=process.env['C2P_STAGE04_RELEASE_FAULT'] === '1';
  if (releaseFault) kernel.call=async(method,params,signal)=>{
    if (method === 'backend.release') throw new Error('test_backend_release_fault');
    return await call(method,params,signal);
  };
  let cutReached=false;
  if (recoveryCut !== 'receipt') kernel.call=async(method,params,signal)=>{
    const atRecord=method === 'task.record_output' && ['before-record','after-record'].includes(recoveryCut);
    const atIngest=method === 'task.ingest' && recoveryCut === 'after-ingest';
    if (!atRecord && !atIngest) return await call(method,params,signal);
    if (recoveryCut !== 'before-record') await call(method,params,signal);
    cutReached=true;
    await kernel.handle.terminate();
    assert.equal(await kernel.handle.waitForExit(AbortSignal.timeout(5_000)),true);
    throw new Error('test_worker_process_cut');
  };
  const run=()=>(multistep ? driver.runMultistepWriter : driver.runSingleWriter)(ctx,{authority,input:descriptor.input,projection,adapter:native,cwd:root,
    ...(compaction ? {compaction:{adapter:auxiliaryNative,providerConfig:auxiliaryProviderConfig,maxTokens:256,config:{auto:false},forceAfterStep:1}} : {}),
    signal:AbortSignal.any([AbortSignal.timeout(300_000),transportDeadline.signal]),verifyComposition:async()=>{await kernel.call('initialize',descriptor.initialize);}});
  const readBudget=():JsonObject=>JSON.parse(py(`${PY_IMPORTS}\nfrom pathlib import Path\nfrom code2paper.agentic.unified_invocation_ledger import read_run_budget_state\nprint(canonical_json_bytes(read_run_budget_state(Path(strict_json_loads(sys.stdin.buffer.read())))).decode())`,
    path.join(root,'run/artifacts/06_authoring/invocations'))) as JsonObject;
  const config=(JSON.parse(readFileSync(descriptor.bootstrap,'utf8')) as {composition_spec:{effective_config:JsonObject}}).composition_spec.effective_config;
  const readBackend=():JsonObject=>JSON.parse(py(`${PY_IMPORTS}\nfrom pathlib import Path\nfrom code2paper.integrations.dsh.task_store import SerialBackendAdmission\nc=strict_json_loads(sys.stdin.buffer.read())\nprint(canonical_json_bytes(SerialBackendAdmission.read_persisted(Path(c['backend_state_root']),c['backend_resource_key'])).decode())`,
    {backend_state_root:config.backend_state_root!,backend_resource_key:config.backend_resource_key!})) as JsonObject;
  if (deniedCompaction) {
    await assert.rejects(run(),/dsh_aux_role_undeclared/);
    const budget=readBudget(),backend=readBackend();
    assert.equal(arrivals.length,2,'calibration plus one navigation; no auxiliary or final send');
    assert.equal(budget.call_count,1);assert.equal(budget.completed_call_count,1);assert.equal(budget.pending_call_count,0);
    assert.equal(budget.spent_input_tokens,17);assert.equal(budget.call_count_by_role && (budget.call_count_by_role as JsonObject).compaction,undefined);
    assert.equal(backend.state,'owned','no complete epoch owner observation was issued');
    writeFileSync(path.join(root,'provider-observations.json'),JSON.stringify(arrivals));
    writeFileSync(path.join(root,'undeclared-compaction-result.json'),JSON.stringify({budget,backend,
      calibration_sends:1,writer_sends:1,auxiliary_sends:0,final_sends:0,original_fees_retained:true}));
    return;
  }
  if (multistep) {
    const receipt=await run();
    const budget=readBudget(),backend=readBackend();
    const state=await kernel.call('task.read',descriptor.scope) as JsonObject;
    assert.equal(receipt.domain_status,'pending_validation');assert.equal(state.state,'terminal');
    const calls=compaction ? 3 : 2;
    assert.equal(budget.call_count,calls);assert.equal(budget.completed_call_count,calls);
    assert.equal(budget.pending_call_count,0);assert.equal(budget.spent_input_tokens,17*calls);
    const totals=JSON.parse(py(`${PY_IMPORTS}\nfrom pathlib import Path\nfrom code2paper.integrations.dsh.artifacts import ArtifactStore,TaskScope\nfrom code2paper.integrations.dsh.writer_contract import ArtifactRefV1,parse_writer_contract\nfrom code2paper.integrations.dsh.epoch_accounting import epoch_totals\nx=strict_json_loads(sys.stdin.buffer.read()); store=ArtifactStore.open_readonly(Path(x['root']),TaskScope(**x['scope']))\nc=parse_writer_contract(canonical_json_bytes(store.read_json(ArtifactRefV1.model_validate(x['contract']))))\nprint(canonical_json_bytes(epoch_totals(store.root/'artifacts/06_authoring/invocations',c)).decode())`,
      {root:path.join(root,'run'),scope:descriptor.scope,contract:contractRef})) as JsonObject;
    assert.deepEqual(totals,{model_requests:calls,input_tokens:17*calls,output_tokens:11*calls,pending_requests:0});
    assert.equal(backend.state,'empty');assert.equal(arrivals.length,calls+1);
    const first=JSON.parse(arrivals[1]!.body) as JsonObject,second=JSON.parse(arrivals[calls]!.body) as JsonObject;
    assert.notDeepEqual(first.messages,second.messages);
    if (!compaction) assert.ok((second.messages as JsonObject[]).some(row=>row.role === 'tool'));
    else {
      assert.ok((second.messages as JsonObject[]).some(row=>typeof row.content==='string' && row.content.includes('Derived summary only:')));
      const frozenText=JSON.stringify(descriptor.input.writer_request.input_payload);
      const expected=JSON.parse(frozenText) as JsonObject;
      assert.ok((second.messages as JsonObject[]).some(row=>{if(typeof row.content!=='string')return false;
        try {return digest(JSON.parse(row.content))===digest(expected);}catch{return false;}}),'actual post-compaction wire retains every frozen payload field');
      const primaryId=(state.binding as JsonObject).session_id;
      const persisted=(state.provider_quiescence as JsonObject).quiescence_ref as JsonObject;
      const snapshot=JSON.parse(py(`${PY_IMPORTS}\nfrom pathlib import Path\nfrom code2paper.integrations.dsh.artifacts import ArtifactStore,TaskScope\nfrom code2paper.integrations.dsh.writer_contract import ArtifactRefV1\nx=strict_json_loads(sys.stdin.buffer.read()); store=ArtifactStore.open_readonly(Path(x['root']),TaskScope(**x['scope']))\nprint(canonical_json_bytes(store.read_json(ArtifactRefV1.model_validate(x['ref']))).decode())`,
        {root:path.join(root,'run'),scope:descriptor.scope,ref:persisted})) as JsonObject;
      assert.equal(snapshot.session_id,primaryId);assert.equal((snapshot.auxiliary_sessions as JsonObject[]).length,1);
    }
    kernel=restartKernel();await kernel.call('initialize',descriptor.initialize);
    const recovered=new driver.KernelAuthority(kernel,{...authority.config,owner:'host:multistep-recovery'});
    assert.deepEqual(await recovered.recoverStoredOutput(ctx),receipt);
    assert.equal(arrivals.length,calls+1);assert.deepEqual(readBudget(),budget);assert.equal(readBackend().state,'empty');
    const sentinel=await closedPythonSentinel();assert.equal(sentinel.model_calls,0);assert.equal(sentinel.network_calls,0);
    writeFileSync(path.join(root,'provider-observations.json'),JSON.stringify(arrivals));
    writeFileSync(path.join(root,'multistep-result.json'),JSON.stringify({receipt,state,budget,backend,totals,
      calibration_sends:1,task_sends:calls,forced_compaction:compaction,navigation_grant_from_actual_wire:true,fresh_worker_recovery:true,
      additional_recovery_sends:0,sentinel}));
    return;
  }
  if (outcome === 'text_stop' || outcome === 'unknown_tool') {
    let failure:Error | undefined;
    await assert.rejects(run(),(error:unknown)=>{assert.ok(error instanceof Error);failure=error;
      assert.equal(error.message,'host_single_terminal_required');return true;});
    const state=await kernel.call('task.read',descriptor.scope) as JsonObject;
    const budget=readBudget();const backend=readBackend();
    writeFileSync(path.join(root,'result.json'),JSON.stringify({receipt:null,state,budget,backend,
      failure:{message:failure!.message,...failure},calibration_sends:1,task_sends:arrivals.length-1}));
    writeFileSync(path.join(root,'provider-observations.json'),JSON.stringify(arrivals));
    assert.equal(arrivals.length,2);assert.equal(state.state,'cancelled');assert.equal(state.receipt,null);
    assert.equal(state.captured_source,null);
    const observation=(failure as Error & {terminalObservation:JsonObject}).terminalObservation;
    assert.equal(observation.source,outcome === 'unknown_tool' ? 'native_unknown_tool; no registered terminal' : 'ordinary_model_text; no tool arguments');
    assert.equal(observation.native_tool_calls,outcome === 'unknown_tool' ? 1 : 0);
    assert.ok(state.provider_quiescence !== null && typeof state.provider_quiescence === 'object');
    assert.equal(budget.call_count,1);assert.equal(budget.spent_input_tokens,17);assert.equal(budget.pending_input_tokens,0);
    assert.equal(backend.state,'empty');
    const release=JSON.parse(py(`${PY_IMPORTS}\nfrom pathlib import Path\nfrom code2paper.integrations.dsh.coverage_use import verify_finished_backend\nc=strict_json_loads(sys.stdin.buffer.read())\nprint(canonical_json_bytes(verify_finished_backend(task_root=Path(c['root']),scope=c['scope'],resource_key=c['resource_key'],backend_binding_digest=digest_json({'state':'empty','owner':None}))).decode())`,
      {root,scope:descriptor.scope,resource_key:config.backend_resource_key!})) as JsonObject;
    assert.equal(release.schema_version,'DshSerialBackendReleaseV1');
    const sentinel=await closedPythonSentinel();assert.equal(sentinel.model_calls,0);assert.equal(sentinel.network_calls,0);
    kernel=restartKernel();await kernel.call('initialize',descriptor.initialize);
    await assert.rejects(kernel.call('task.claim',{...descriptor.scope,owner:'host:text-resend'}),/task_claim_held/);
    assert.equal(arrivals.length,2);assert.deepEqual(readBudget(),budget);assert.equal(readBackend().state,'empty');
    writeFileSync(path.join(root,outcome === 'unknown_tool' ? 'unknown-tool-release.json' : 'text-stop-release.json'),JSON.stringify({release,sentinel,new_worker:true,additional_sends:0}));
    return;
  }
  if (['cap_drift','composition_drift','budget_exhausted'].includes(outcome)) {
    const driftPath=path.join(root,'cordis.yml');
    const originalConfig=outcome === 'composition_drift' ? readFileSync(driftPath) : undefined;
    if (originalConfig) writeFileSync(driftPath,Buffer.concat([originalConfig,Buffer.from('\n# drift after prepare\n')]));
    let refusal:string | undefined;
    await assert.rejects(run(),(error:unknown)=>{assert.ok(error instanceof Error);refusal=error.message;return true;});
    assert.match(refusal!,outcome === 'cap_drift' ? /writer_cap_mismatch/ : outcome === 'composition_drift' ?
      /composition_drift/ : /unified_invocation_budget_exceeded:calls:writer:1>0/);
    if (outcome === 'cap_drift') {
      assert.equal(projection.post_clamp_max_output_tokens,4096);
      assert.equal(loopRequests.length,2);assert.equal(loopRequests[1]!.maxTokens,4095);
    }
    assert.equal(arrivals.length,1,'only C00 calibration; no formal provider arrival');
    const before=readBudget();assert.equal(before.call_count,0);assert.equal(before.pending_call_count,0);
    assert.equal(before.spent_input_tokens,0);
    if (originalConfig) writeFileSync(driftPath,originalConfig);
    await kernel.close();kernel=restartKernel();await kernel.call('initialize',descriptor.initialize);
    const state=await kernel.call('task.read',descriptor.scope) as JsonObject;
    assert.equal(state.state,outcome === 'composition_drift' ? 'outbox' : 'cancelled');assert.equal(state.receipt,null);
    assert.deepEqual(readBudget(),before);assert.equal(arrivals.length,1);
    const sentinel=JSON.parse(readFileSync(path.join(root,'python-sentinel.json'),'utf8')) as JsonObject;
    assert.equal(sentinel.probe_refused,true);assert.equal(sentinel.model_calls,0);assert.equal(sentinel.network_calls,0);
    writeFileSync(path.join(root,'provider-observations.json'),JSON.stringify(arrivals));
    writeFileSync(path.join(root,'result.json'),JSON.stringify({receipt:null,refusal_reason:refusal,budget:before,sentinel,
      calibration_sends:1,task_sends:0,new_worker:true}));
    return;
  }
  let damagedRaw:{path:string;bytes:Buffer} | undefined;
  if (['provider_error','provider_error_cached_usage','finish_without_usage','usage_without_finish','disconnect','timeout'].includes(outcome)) {
    let observation:JsonObject|undefined;
    await assert.rejects(run(),(error:unknown)=>{
      assert.ok(error instanceof Error);
      if (['provider_error','provider_error_cached_usage'].includes(outcome)) assert.equal(error.message,'host_provider_stream_error');
      const failure=error as Error & {terminalObservation:JsonObject;providerError:JsonObject};
      observation=failure.terminalObservation;
      if (outcome==='timeout') assert.equal(error.message,'host_cancelled');
      else assert.ok(observation);
      if (['provider_error','provider_error_cached_usage'].includes(outcome)) {
        assert.equal(observation.source,'native_provider_error; no terminal');
        assert.equal(observation.native_tool_calls,0);
        assert.equal(failure.providerError.message,'Controlled provider stream failure');
      }
      writeFileSync(path.join(root,'first-failure.json'),JSON.stringify({primary:error.message,
        provider_error:failure.providerError,terminal:observation}));
      return true;
    });
    assert.equal(arrivals.length,2);
    const retained=readBudget();assert.equal(retained.call_count,1);
    assert.equal(retained.pending_call_count,1);assert.equal(retained.completed_call_count,0);
    assert.equal(retained.spent_input_tokens,0);assert.ok(Number(retained.pending_input_tokens)>0);
    assert.equal(retained.provider_usage_status,['provider_error_cached_usage','usage_without_finish'].includes(outcome) ? 'validated' : 'partial');
    const state=await kernel.call('task.read',descriptor.scope) as JsonObject;
    assert.equal(state.state,'cancelled');assert.equal(state.receipt,null);
    assert.equal(state.captured_source,null);assert.equal(state.provider_quiescence,null);
    const backend=readBackend();assert.equal(backend.state,'owned');
    let sessionRef=observation?.session_ref;
    if (outcome==='timeout') {
      assert.equal(transportDeadline.signal.aborted,true);assert.equal(providerUnfinished,true);
      assert.equal(server.listening,true);
      await ctx.sessionPersistence.flush();
      const binding=state.binding as JsonObject;const sid=String(binding.session_id);
      const files=readdirSync(path.join(root,'sessions'),{recursive:true}).filter(name=>
        typeof name==='string' && name.endsWith(`${sid}/session.v4.jsonl`));
      assert.equal(files.length,1);
      const bytes=readFileSync(path.join(root,'sessions',String(files[0])),'utf8');
      const rows=bytes.trim().split('\n').map(line=>JSON.parse(line) as JsonObject);
      assert.equal(rows[0]!.id,sid);assert.equal(rows[0]!.version,4);
      assert.equal(rows.some(row=>row.type==='tool/call' || row.type==='tool/result'),false);
      sessionRef=await put({schema_version:'DshSessionCaptureV1',session_id:sid,format_version:'SessionFileV4',events:rows.slice(1)});
      writeFileSync(path.join(root,'timeout-session-readback.json'),JSON.stringify({session_id:sid,
        original_session_file:path.join(root,'sessions',String(files[0])),session_ref:sessionRef,
        timeout_after_provider_arrival:true,client_aborted:true,provider_still_listening:true,provider_completion_unproven:true}));
    }
    assert.ok(sessionRef!==undefined);
    await assert.rejects(kernel.call('backend.release',{...descriptor.scope,
      quiescence_ref:sessionRef}),/backend_release_accounting_unsettled/);
    await kernel.close();kernel=restartKernel();await kernel.call('initialize',descriptor.initialize);
    assert.deepEqual(readBudget(),retained);assert.deepEqual(readBackend(),backend);
    const reread=await kernel.call('task.read',descriptor.scope) as JsonObject;
    assert.equal(reread.provider_quiescence,null);assert.equal(reread.captured_source,null);assert.equal(reread.receipt,null);
    await assert.rejects(kernel.call('task.claim',{...descriptor.scope,owner:'host:provider-error-resend'}),/task_claim_held/);
    const recovered=new driver.KernelAuthority(kernel,{scope:descriptor.scope as unknown as DriverApi.KernelTaskScope,
      caller:{executionId:String(descriptor.scope.execution_id),runId:'stage04-real',hostGeneration:2},
      owner:'host:provider-error-recovery',compositionDigest:descriptor.composition_digest,contractRef,budgetRef:descriptor.budget_ref});
    await assert.rejects(recovered.recoverStoredOutput(ctx),/kernel_recorded_output_not_ready/);
    assert.deepEqual(readBudget(),retained);assert.deepEqual(readBackend(),backend);assert.equal(arrivals.length,2);
    const sentinel=JSON.parse(readFileSync(path.join(root,'python-sentinel.json'),'utf8')) as JsonObject;
    assert.equal(sentinel.probe_refused,true);assert.equal(sentinel.model_calls,0);assert.equal(sentinel.network_calls,0);
    writeFileSync(path.join(root,'provider-observations.json'),JSON.stringify(arrivals));
    writeFileSync(path.join(root,'result.json'),JSON.stringify({receipt:null,budget:retained,backend,
      provider_usage:outcome === 'provider_error_cached_usage' ? 'observed-input0-output3; finish unproven'
        : outcome === 'usage_without_finish' ? 'observed-input17-output3; finish unproven' : 'unobserved',calibration_sends:1,task_sends:1,sentinel,
      recovery:{new_worker:true,additional_sends:0,reservation_retained:true,provider_quiescence_unproven:true}}));
    return;
  }
  const rawDamaged=outcome === 'raw_missing' || outcome === 'raw_corrupt';
  if (rawDamaged) kernel.call=async(method,params,signal)=>{
    if (method === 'task.record_output' && damagedRaw === undefined) {
      const envelope=(params as JsonObject).envelope as JsonObject;
      const ref=(envelope.adapter_arguments as JsonObject).ref as JsonObject;
      const file=path.join(root,'run/dsh-artifacts',digest(descriptor.scope).slice(7),String(ref.artifact_id).slice(7));
      const bytes=readFileSync(file);assert.ok(bytes.length>0);
      damagedRaw={path:file,bytes};
      if (outcome === 'raw_missing') unlinkSync(file);
      else {const corrupt=Buffer.from(bytes);corrupt[0]=corrupt[0]! ^ 1;writeFileSync(file,corrupt);}
    }
    return await call(method,params,signal);
  };
  if (outcome === 'cancel') {
    const abort=new AbortController();cancelFormal=()=>abort.abort(new Error('test_cancel_after_provider_arrival'));
    await assert.rejects(driver.runSingleWriter(ctx,{authority,input:descriptor.input,projection,adapter:native,cwd:root,
      signal:AbortSignal.any([abort.signal,AbortSignal.timeout(300_000)]),
      verifyComposition:async()=>{await kernel.call('initialize',descriptor.initialize);}}));
    assert.equal(abort.signal.aborted,true);assert.equal(providerUnfinished,true);assert.equal(server.listening,true);
    assert.equal(arrivals.length,2);
    const readBudget=():JsonObject=>JSON.parse(py(`${PY_IMPORTS}\nfrom pathlib import Path\nfrom code2paper.agentic.unified_invocation_ledger import read_run_budget_state\nprint(canonical_json_bytes(read_run_budget_state(Path(strict_json_loads(sys.stdin.buffer.read())))).decode())`,
      path.join(root,'run/artifacts/06_authoring/invocations'))) as JsonObject;
    const before=readBudget();
    assert.equal(before.call_count,1);assert.equal(before.spent_input_tokens,0);
    assert.ok(Number(before.pending_input_tokens)>0);assert.equal(before.completed_receipt_count,0);
    // A wait API fault proves no scope exit. Only this API result is injected;
    // the actual worker/Host/provider and original pending fee remain real.
    const kernelApi=await import(pathToFileURL(path.join(staged,'lib/kernel-client.js')).href) as typeof KernelApi;
    let cleanupSignal:AbortSignal | undefined;
    const waitFault=new kernelApi.KernelClient(new Proxy(kernel.handle,{get(target,key){
      if (key === 'waitForExit') return async(signal:AbortSignal)=>{
        cleanupSignal=signal;assert.equal(signal.aborted,false);throw new Error('test_wait_api_fault');
      };
      const value:unknown=Reflect.get(target,key);
      return typeof value === 'function' ? value.bind(target) : value;
    }}));
    await assert.rejects(waitFault.close(),/test_wait_api_fault/);
    assert.ok(cleanupSignal !== undefined);assert.notEqual(cleanupSignal,abort.signal);
    assert.deepEqual(readBudget(),before);assert.equal(server.listening,true);assert.equal(arrivals.length,2);
    writeFileSync(path.join(root,'wait-api-fault.json'),JSON.stringify({fault_injected:true,close_rejected:true,
      worker_scope_quiescent_observed:false,remote_provider_quiescent_observed:false,fee_state:before}));
    await kernel.close();kernel=restartKernel();await kernel.call('initialize',descriptor.initialize);
    const state=await kernel.call('task.read',descriptor.scope) as JsonObject;
    assert.equal(state.state,'cancelled');assert.equal(state.receipt,null);
    await assert.rejects(kernel.call('task.claim',{...descriptor.scope,owner:'host:cancel-resend'}),/task_claim_held/);
    const recovered=new driver.KernelAuthority(kernel,{scope:descriptor.scope as unknown as DriverApi.KernelTaskScope,
      caller:{executionId:String(descriptor.scope.execution_id),runId:'stage04-real',hostGeneration:2},owner:'host:cancel-recovery',
      compositionDigest:descriptor.composition_digest,contractRef,budgetRef:descriptor.budget_ref});
    await assert.rejects(recovered.recoverStoredOutput(ctx),/kernel_recorded_output_not_ready/);
    assert.deepEqual(readBudget(),before);assert.equal(arrivals.length,2);assert.equal(server.listening,true);
    const sentinel=JSON.parse(readFileSync(path.join(root,'python-sentinel.json'),'utf8')) as JsonObject;
    assert.equal(sentinel.probe_refused,true);assert.equal(sentinel.model_calls,0);assert.equal(sentinel.network_calls,0);
    writeFileSync(path.join(root,'provider-observations.json'),JSON.stringify(arrivals));
    writeFileSync(path.join(root,'result.json'),JSON.stringify({receipt:null,budget:before,calibration_sends:1,task_sends:1,sentinel,
      cancellation:{after_provider_arrival:true,client_aborted:true,provider_scope_unproven:true,provider_still_listening:true},
      recovery:{new_worker:true,lost_capability:true,additional_sends:0,reservation_retained:true}}));
    return;
  }
  let receipt:JsonObject;
  const contentRefused=['invalid_content','wrong_formula_binding','wrong_atom_binding','inline_formula','formula_metadata','missing_witness','packet10_original'].includes(outcome);
  let refusalReason:string | undefined;
  if (contentRefused) {
    await assert.rejects(run(),(error:unknown)=>{
      assert.ok(error instanceof Error);refusalReason=error.message;
      writeFileSync(path.join(root,'first-failure.json'),JSON.stringify({primary:refusalReason,
        terminal:(error as Error & {terminalObservation?: unknown}).terminalObservation ?? null,
        secondary:(error as Error & {cleanupFailures?: unknown}).cleanupFailures ?? []}));
      if (releaseFault) {
        const failures=(error as Error & {cleanupFailures?: {stage:string;message:string}[]}).cleanupFailures;
        assert.ok(failures?.some(f=>f.stage === 'backend.release' && f.message === 'test_backend_release_fault'));
        writeFileSync(path.join(root,'first-failure.json'),JSON.stringify({primary:refusalReason,secondary:failures}));
      }
      return true;
    });
    if (['packet10_original','missing_witness'].includes(outcome)) assert.equal(refusalReason,'schema_invalid');
    else if (['invalid_content','inline_formula','formula_metadata'].includes(outcome)) assert.match(refusalReason!,/^publication_section_binding_failed:formula_placeholder:/);
    else if (outcome === 'wrong_formula_binding') assert.match(refusalReason!,/formula_placeholder_unknown_package/);
    else if (outcome === 'wrong_atom_binding') assert.match(refusalReason!,/^publication_paragraph_transaction_failed:unknown_atom_witness:/);
    else assert.equal(refusalReason,'writer_content_rejected');
    assert.equal(cutReached,false);receipt={};
  } else if (rawDamaged) {
    await assert.rejects(run(),outcome === 'raw_missing' ? /artifact_unavailable/ : /artifact_bytes_mismatch/);
    assert.ok(damagedRaw);assert.equal(arrivals.length,2);
    const retained=readBudget();assert.equal(retained.call_count,1);assert.equal(retained.pending_call_count,1);
    assert.ok(Number(retained.pending_input_tokens)>0);assert.equal(retained.spent_input_tokens,0);
    writeFileSync(damagedRaw.path,damagedRaw.bytes);
    await kernel.close();kernel=restartKernel();await kernel.call('initialize',descriptor.initialize);
    const recovered=new driver.KernelAuthority(kernel,{scope:descriptor.scope as unknown as DriverApi.KernelTaskScope,
      caller:{executionId:String(descriptor.scope.execution_id),runId:'stage04-real',hostGeneration:2},owner:'host:damaged-raw-recovery',
      compositionDigest:descriptor.composition_digest,contractRef,budgetRef:descriptor.budget_ref});
    await assert.rejects(recovered.recoverStoredOutput(ctx),/task_mutation_closed/);
    const state=await kernel.call('task.read',descriptor.scope) as JsonObject;
    assert.equal(state.state,'cancelled');assert.equal(state.receipt,null);
    assert.deepEqual(readBudget(),retained);assert.equal(arrivals.length,2);
    const sentinel=JSON.parse(readFileSync(path.join(root,'python-sentinel.json'),'utf8')) as JsonObject;
    assert.equal(sentinel.probe_refused,true);assert.equal(sentinel.model_calls,0);assert.equal(sentinel.network_calls,0);
    writeFileSync(path.join(root,'provider-observations.json'),JSON.stringify(arrivals));
    writeFileSync(path.join(root,'result.json'),JSON.stringify({receipt:null,budget:retained,sentinel,
      calibration_sends:1,task_sends:1,raw_damage:outcome,original_bytes_restored:true,
      recovery:{new_worker:true,additional_sends:0,reservation_retained:true,domain_mutation_closed:true}}));
    return;
  } else if (recoveryCut === 'receipt') receipt=await run();
  else {await assert.rejects(run());assert.equal(cutReached,true);receipt={};}
  const backendBeforeRecovery=readBackend();
  assert.equal(backendBeforeRecovery.state,releaseFault || recoveryCut !== 'receipt' ? 'owned' : 'empty');
  if (backendBeforeRecovery.state === 'owned') {
    assert.deepEqual(backendBeforeRecovery.owner,{schema_version:'serial-backend-admission/1',
      execution_id:descriptor.scope.execution_id,run_root:path.join(root,'run'),resource_key:config.backend_resource_key});
  }
  if (recoveryCut === 'receipt') await kernel.close();
  kernel=restartKernel();
  await kernel.call('initialize',descriptor.initialize);
  const recovered=new driver.KernelAuthority(kernel,{scope:descriptor.scope as unknown as DriverApi.KernelTaskScope,
    caller:{executionId:String(descriptor.scope.execution_id),runId:'stage04-real',hostGeneration:2},owner:'host:stage04-recovery',
    compositionDigest:descriptor.composition_digest,contractRef,budgetRef:descriptor.budget_ref});
  if (contentRefused) await assert.rejects(recovered.recoverStoredOutput(ctx),/task_mutation_closed/);
  else {
    const recoveredReceipt=await recovered.recoverStoredOutput(ctx);
    if (recoveryCut === 'receipt' && !rawDamaged) assert.deepEqual(recoveredReceipt,receipt);
    else receipt=recoveredReceipt;
  }
  assert.equal(arrivals.length,2,'one C00 calibration, one production task dispatch');
  const state=await kernel.call('task.read',descriptor.scope) as JsonObject;
  if (contentRefused) {assert.equal(state.state,'cancelled');assert.equal(state.receipt,null);}
  else {
    assert.equal(receipt.domain_status,outcome === 'draft' ? 'pending_validation' : outcome === 'research_required' ? 'waiting' : 'blocked');
    assert.equal(state.state,'terminal');assert.deepEqual(state.receipt,receipt);
    if (outcome === 'unicode') assert.equal((receipt.detail as JsonObject).reason,unicodeReason);
  }
  const budget=JSON.parse(py(`${PY_IMPORTS}\nfrom pathlib import Path\nfrom code2paper.agentic.unified_invocation_ledger import read_run_budget_state\nprint(canonical_json_bytes(read_run_budget_state(Path(strict_json_loads(sys.stdin.buffer.read())))).decode())`,path.join(root,'run/artifacts/06_authoring/invocations'))) as JsonObject;
  assert.equal(budget.call_count,1);assert.equal(budget.spent_input_tokens,17);assert.equal(budget.pending_input_tokens,0);
  const backend=readBackend();
  assert.equal(backend.state,'empty','healthy recovery consumes the original registered finish, including a prior release failure');
  const backendRelease=JSON.parse(py(`${PY_IMPORTS}\nfrom pathlib import Path\nfrom code2paper.integrations.dsh.coverage_use import verify_finished_backend\nc=strict_json_loads(sys.stdin.buffer.read())\nprint(canonical_json_bytes(verify_finished_backend(task_root=Path(c['root']),scope=c['scope'],resource_key=c['resource_key'],backend_binding_digest=digest_json({'state':'empty','owner':None}))).decode())`,
    {root,scope:descriptor.scope,resource_key:config.backend_resource_key!})) as JsonObject;
  assert.equal(backendRelease.schema_version,'DshSerialBackendReleaseV1');
  // Replace the actual subprocess, discard the original private capability,
  // and replay from durable kernel facts. No Agent or adapter is created.
  if (contentRefused) await assert.rejects(recovered.recoverStoredOutput(ctx),/task_mutation_closed/);
  else assert.deepEqual(await recovered.recoverStoredOutput(ctx),receipt);
  assert.equal(arrivals.length,2,'receipt replay must never reach the provider');
  const sentinel=await closedPythonSentinel();
  writeFileSync(path.join(root,'provider-observations.json'),JSON.stringify(arrivals));
  writeFileSync(path.join(root,'result.json'),JSON.stringify({receipt:contentRefused ? null : receipt,refusal_reason:refusalReason,
    budget,backend_before_recovery:backendBeforeRecovery,backend,backend_release:backendRelease,calibration_sends:1,task_sends:1,sentinel,
    recovery:{cut:recoveryCut,new_worker:true,lost_capability:true,receipt_identical:!contentRefused,additional_sends:0}}));
});
