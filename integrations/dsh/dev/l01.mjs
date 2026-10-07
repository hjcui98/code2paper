/** B L01: one bounded native DSH request, with offline-only wire calibration. */
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {createServer} from 'node:http';
import {readFileSync,writeFileSync,mkdirSync,chmodSync,existsSync,symlinkSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {boot,loadOverlayPatches,loadProfileDirectory} from '@deepseek-ai/dsh-app-boot';
import {provideCmdline} from '@deepseek-ai/dsh-cmdline';
import {createUserMessage} from '@deepseek-ai/dsh-llm';
import * as PiAi from '@deepseek-ai/dsh-llm-pi-ai';

const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
const [mode,output,receiptPath,authorizationPath,failureFixture]=process.argv.slice(2);
assert.ok(['prepare','offline','live'].includes(mode),'choose prepare|offline|live OUTPUT [RECEIPT AUTHORIZATION]');
assert.ok(!failureFixture || (mode==='offline' && ['stream-finalization','terminal-rejection','provider-error'].includes(failureFixture)),'failure fixture is offline only');
assert.ok(output && path.isAbsolute(output) && output.startsWith('/tmp/') && output!=='/tmp');
const profilePath=path.join(repo,'tests/live/profiles/qwen38_dsh_l01.json');
const profile=JSON.parse(readFileSync(profilePath,'utf8'));
const candidate=profile.candidate??'0.2.0-rc.1+loop-origin.1';
// Provider identity keeps the original shared admission database across
// runtime revisions. A new candidate is not permission to bypass an owner.
const originalBackendCandidate='0.2.0-rc.1+loop-origin.1';
if ((profile.backend_admission_candidate===undefined?originalBackendCandidate:profile.backend_admission_candidate)!==originalBackendCandidate) throw new Error('l01_backend_alias_forbidden');
const canonicalBackend=path.join(repo,'.dsh-dev/candidates',originalBackendCandidate,'live-backend-admission');
const dev=path.join(repo,'.dsh-dev/candidates',candidate), runtime=path.join(dev,'runtime');
const staged=path.join(dev,'home/profiles/node_modules/@code2paper/dsh-bundle');
const python=path.join(dev,'pyworker/bin/python'), worker=path.join(repo,'integrations/dsh/dev/l01_worker.py');
const sha=raw=>'sha256:'+createHash('sha256').update(raw).digest('hex');
const save=(name,value)=>writeFileSync(path.join(output,name),JSON.stringify(value,null,2)+'\n');
const env={...process.env,PYTHONPATH:path.join(repo,'src'),PYTHONDONTWRITEBYTECODE:'1'};
delete env.OPENAI_API_KEY;delete env.DEEPSEEK_API_KEY;
const py=(flag,value)=>{const result=spawnSync(python,[worker,flag],{cwd:repo,env,input:JSON.stringify(value),encoding:'utf8',maxBuffer:4<<20});
  assert.equal(result.status,0,result.stderr);return JSON.parse(result.stdout);};
const digest=value=>py('--action',{action:'digest',value});
const seal=value=>py('--action',{action:'seal',value});
// Local unkeyed engine: explicit public placeholder, never inherited credentials.
process.env.C2P_L01_LOCAL_PLACEHOLDER='local-unused-placeholder';
const originalFetch=globalThis.fetch;
let ctx,kernel,server,native,descriptor,projection,packet,operationFailure;
let sends=0,bodyChunks=[],loopRequests=[],streamFacts,streamFailure;
let workerClosed=false;let monitor;let metricsInflight=false;const pressureStop=new AbortController();
const config=path.join(output,'cordis.yml'), overlay=path.join(output,'overlay.json');
const launcher=path.join(output,'python-worker');
const wirePath=path.join(output,'provider-wire.json');
const taskRoot=path.join(output,'task');
const tokenPath=path.join(taskRoot,'tokenizer-receipt.json');
const pkg=path.join(repo,'integrations/dsh');
const profileDir=path.join(dev,'home/profiles/code2paper-dev-compat');
const kernelApi=await import(pathToFileURL(path.join(staged,'lib/kernel-client.js')).href);
const writer=await import(pathToFileURL(path.join(staged,'lib/writer-request.js')).href);
const driver=await import(pathToFileURL(path.join(staged,'lib/workflow-driver.js')).href);
const bindFile=file=>({path:file,bytes_digest:sha(readFileSync(file)),byte_length:readFileSync(file).length});
const put=async value=>kernel.call('artifact.record',{...descriptor.scope,media_type:'application/json',
  raw_base64:Buffer.from(typeof value==='string'?value:JSON.stringify(value)).toString('base64')});

async function preflight(){
  const facts={at:new Date().toISOString(),inference_requests:0};
  for(const suffix of ['/health','/v1/models','/metrics']){
    const res=await originalFetch('http://127.0.0.1:8006'+suffix,{signal:AbortSignal.timeout(5000)});
    facts[suffix]={status:res.status}; assert.equal(res.status,200,suffix);
    const raw=await res.text(); assert.ok(raw.length<2<<20);
    if(suffix==='/v1/models'){const models=JSON.parse(raw);assert.ok(models.data.some(x=>x.id===profile.model));facts[suffix].model_ids=models.data.map(x=>x.id);}
    if(suffix==='/metrics'){
      const lines=raw.split('\n').filter(x=>!x.startsWith('#') && /num_requests_running|num_requests_waiting|kv_cache_usage_perc|gpu_cache_usage_perc/.test(x));
      facts[suffix].observations=lines;
      const queues=lines.filter(x=>/num_requests_running|num_requests_waiting/.test(x));
      assert.ok(queues.length>=2,'running/waiting metrics required for exclusive L01');
      assert.ok(queues.every(x=>Number(x.trim().split(/\s+/).at(-1))===0),'model queue must be idle');
      assert.ok(lines.filter(x=>/cache_usage_perc/.test(x)).every(x=>Number(x.trim().split(/\s+/).at(-1))<0.9));
    }
  }
  save('runtime-preflight.json',facts);return facts;
}

function observeFetch(){
  globalThis.fetch=async(input,init)=>{
    const url=typeof input==='string'?input:input instanceof URL?input.href:input.url;
    assert.equal(url,profile.base_url+'/chat/completions','no other model endpoint');
    assert.equal(init?.method?.toUpperCase(),'POST');assert.equal(typeof init.body,'string');
    assert.equal(init.body,readFileSync(wirePath,'utf8'),'exact calibrated provider wire');
    assert.equal(++sends,1,'one primary; no retry/probe');
    bodyChunks.push(init.body);save('dispatch-observation.json',{requests:sends,body:bindFile(wirePath),at:new Date().toISOString()});
    const res=await originalFetch(input,init);const reader=res.body?.getReader();
    assert.ok(reader);const raw=[];let size=0;
    const stream=new ReadableStream({async pull(controller){
      try{
        const item=await reader.read();
        if(item.done){
          const bytes=Buffer.concat(raw);writeFileSync(path.join(output,'provider-response.sse'),bytes);
          const events=bytes.toString('utf8').split('\n').filter(x=>x.startsWith('data: ') && x!=='data: [DONE]').map(x=>JSON.parse(x.slice(6)));
          const usages=events.filter(x=>x.usage);const finishes=events.flatMap(x=>x.choices??[]).filter(x=>x.finish_reason);
          const providerErrors=events.filter(x=>x.error).map(x=>x.error);
          streamFacts={http_status:res.status,usage:usages.at(-1)?.usage??null,finish_reasons:finishes.map(x=>x.finish_reason),
            provider_errors:providerErrors};
          save('provider-observation.json',streamFacts);
          if(providerErrors.length){
            const failure=new Error('l01_provider_sse_error');
            failure.providerErrors=providerErrors;
            throw failure;
          }
          assert.equal(res.status,200);assert.equal(usages.length,1,'missing/duplicate raw usage refused');
          assert.ok(Number.isSafeInteger(streamFacts.usage.prompt_tokens) && streamFacts.usage.prompt_tokens>0);
          assert.ok(Number.isSafeInteger(streamFacts.usage.completion_tokens) && streamFacts.usage.completion_tokens>=0);
          assert.ok(streamFacts.usage.prompt_tokens<=profile.input_token_cap);
          assert.ok(streamFacts.usage.completion_tokens<=profile.max_output_tokens);
          if(mode==='live') assert.equal(streamFacts.usage.prompt_tokens,JSON.parse(readFileSync(tokenPath,'utf8')).input_tokens,'actual usage must match exact-wire tokenizer');
          // Transport completion is independent of the required Writer tool.
          // Ordinary stop is rejected by the Host, never parsed as tool JSON.
          assert.ok(finishes.length===1 && ['tool_calls','stop'].includes(finishes[0].finish_reason));
          controller.close();return;
        }
        size+=item.value.length;assert.ok(size<=4<<20,'bounded SSE observation');raw.push(Buffer.from(item.value));controller.enqueue(item.value);
      }catch(error){
        streamFailure??={type:error.constructor.name,message:error.message,
          ...(error.providerErrors ? {provider_errors:error.providerErrors} : {})};
        save('provider-stream-failure.json',streamFailure);
        await reader.cancel(error);controller.error(error);
      }
    },cancel:reason=>reader.cancel(reason)});
    return new Response(stream,{status:res.status,statusText:res.statusText,headers:res.headers});
  };
}

async function makeProjection(binding,loop,wire){
  const loopRef=await put(loop),providerRef=await put(wire);
  const comparison=await put({binding,loop_digest:loopRef.bytes_digest,provider_digest:providerRef.bytes_digest});
  const equivalence=await put({schema_version:'WriterWireEquivalenceV1',input_digest:descriptor.input.input_digest,
    renderer_digest:descriptor.input.renderer_digest,composition_digest:descriptor.composition_digest,
    projection_material_digest:digest(binding),loop_request_ref:loopRef,provider_wire_ref:providerRef,comparison_ref:comparison,
    transport_whitelist:['request.signal','request.sessionId','messages.id','messages.createdAt']});
  const tokens=JSON.parse(readFileSync(tokenPath,'utf8'));
  const measurement=await put({schema_version:'WriterMeasurementV1',input_digest:descriptor.input.input_digest,
    renderer_digest:descriptor.input.renderer_digest,tokenizer_digest:descriptor.tokenizer_digest,
    meter_version:'vllm-exact-dsh-wire-receipt/2',measured_input_tokens:tokens.input_tokens,context_tokens:profile.context_tokens,
    safety_margin_tokens:512,thinking_tokens:descriptor.writer_thinking_tokens,post_clamp_max_output_tokens:profile.max_output_tokens,
    measured_wire_digest:providerRef.bytes_digest});
  return seal({schema_version:'WriterWireProjectionV1',protocol_version:'c2p-dsh/1',...binding,
    renderer_version:descriptor.input.renderer_version,task_view_digest:digest(descriptor.input.writer_request.input_payload),
    terminal_schema_digest:digest(descriptor.input.terminal_schema),measurement_ref:measurement,wire_equivalence_ref:equivalence});
}

async function execute(){
  const projectionRef=await put(projection);
  const contractRef=await kernel.call('task.prepare',{...descriptor.scope,frozen_ref:descriptor.frozen_ref,projection_ref:projectionRef,cap:profile.max_output_tokens});
  const authority=new driver.KernelAuthority(kernel,{scope:descriptor.scope,
    caller:{executionId:descriptor.scope.execution_id,runId:'l01',hostGeneration:1},owner:'host:l01',
    compositionDigest:descriptor.composition_digest,contractRef,budgetRef:descriptor.budget_ref});
  const result=await driver.runSingleWriter(ctx,{authority,input:descriptor.input,projection,adapter:native,cwd:output,
    signal:AbortSignal.any([AbortSignal.timeout(profile.wall_seconds*1000),pressureStop.signal]),verifyComposition:()=>kernel.call('initialize',descriptor.initialize)});
  assert.equal(sends,1);return result;
}

try{
  if(mode==='live'){
    assert.ok(receiptPath && authorizationPath,'current coverage and concrete authorization required');
    packet=JSON.parse(readFileSync(path.join(output,'packet.json'),'utf8'));
    const authorization=JSON.parse(readFileSync(authorizationPath,'utf8'));
    assert.equal(authorization.schema_version,'L01OperatorAuthorizationV1');assert.equal(authorization.approved,true);
    assert.equal(authorization.packet_digest,sha(readFileSync(path.join(output,'packet.json'))));
    assert.equal(authorization.model,profile.model);assert.equal(authorization.primary_requests,1);
    assert.equal(authorization.input_token_cap,32768);assert.equal(authorization.max_output_tokens,4096);
    assert.equal(authorization.wall_seconds,180);assert.equal(authorization.retries,0);
    for(const bound of packet.frozen_files) assert.deepEqual(bindFile(bound.path),bound);
    const admission=py('--action',{action:'admit',receipt:receiptPath,engine_root:repo,candidate});save('coverage-admission.json',admission);
    assert.equal(admission.engine_digest,packet.engine_digest);
    await preflight();
    assert.ok(!existsSync(path.join(output,'live-started.json')),'never repeat a started request');
    py('--action',{action:'tokenize',wire_path:wirePath,receipt_path:tokenPath});
    descriptor=JSON.parse(readFileSync(path.join(output,'descriptor.json'),'utf8'));
  }else{
    assert.ok(!existsSync(config),'fresh output only');mkdirSync(output,{recursive:true});
    mkdirSync(path.join(output,'node_modules/@code2paper'),{recursive:true});
    symlinkSync(path.join(runtime,'node_modules/@deepseek-ai'),path.join(output,'node_modules/@deepseek-ai'),'dir');
    symlinkSync(staged,path.join(output,'node_modules/@code2paper/dsh-bundle'),'dir');
    writeFileSync(config,readFileSync(path.join(profileDir,'cordis.yml')));
    writeFileSync(overlay,JSON.stringify([{id:'web-runtime',config:{printUrl:false,openBrowser:false,surfaceContext:false,trustedHosts:[]}},
      {id:'session-persistence-jsonl',config:{root:path.join(output,'sessions'),compression:'none'}}]));
    const quote=x=>"'"+x.replaceAll("'","'\\''")+"'";
    writeFileSync(launcher,`#!/bin/sh\nexec ${quote(python)} ${quote(worker)} "$@"\n`);chmodSync(launcher,0o700);
    const files={loader:path.join(runtime,'node_modules/@deepseek-ai/cordis-plugin-loader/lib/index.js'),
      peer:path.join(pkg,'node_modules/@deepseek-ai/dsh-llm/package.json'),bundle_source:path.join(pkg,'src/index.ts'),bundle_lock:path.join(pkg,'package-lock.json'),
      build_input:path.join(pkg,'dev/toolchain/tsconfig.build.json'),bundle_js:path.join(staged,'lib/index.js'),build_receipt:path.join(staged,'lib/build-receipt.json'),
      stage:path.join(dev,'staging.json'),node:process.execPath,preset:path.join(staged,'presets/code2paper.patch.yml'),persona:path.join(staged,'lib/task-tools.js'),
      tool_schema:path.join(pkg,'wire-v1/native-terminal.schema.json'),renderer:path.join(staged,'lib/writer-request.js'),python_executable:python,
      python_environment:path.join(dev,'pyworker/pyvenv.cfg'),python_dependencies:path.join(pkg,'dev/pyworker-requirements.lock'),
      worker:path.join(repo,'src/code2paper/integrations/dsh/worker.py'),tokenizer:worker,meter:worker,
      l01_worker:worker,l01_driver:fileURLToPath(import.meta.url),l01_profile:profilePath,
      test_worker_launcher:launcher,host_config:config,host_overlay:overlay,host_profile:path.join(profileDir,'cordis.yml'),
      host_profile_package:path.join(profileDir,'package.json'),host_profile_patch:path.join(profileDir,'cordis.patch.yml'),host_offline_policy:path.join(pkg,'dev/offline.patch.yml')};
    const trees={runtime:path.join(runtime,'node_modules'),dependencies:path.join(pkg,'node_modules'),python_runtime:path.join(dev,'pyworker/lib/python3.13/site-packages'),host_profile_runtime:profileDir,staged_bundle:staged};
    descriptor=py('--prepare',{root:taskRoot,engine_root:repo,backend_state_root:mode==='offline'?path.join(taskRoot,'backend'):canonicalBackend,
      network_mode:mode==='offline'?'isolated_fake':'live_packet',files,trees});save('descriptor.json',descriptor);
    // Port8006 is used ONLY inside unshare-net; never bind the host engine port.
    assert.ok(process.env.C2P_L01_PARENT_NETNS,'original offline namespace proof required');
    const parentNamespace=JSON.parse(process.env.C2P_L01_PARENT_NETNS);
    py('--action',{action:'namespace',parent:parentNamespace});
    server=createServer((request,response)=>{let body='';request.setEncoding('utf8');request.on('data',x=>body+=x);request.on('end',()=>{
      bodyChunks.push(body);
      const args=failureFixture==='terminal-rejection' && bodyChunks.length>1 ?
        readFileSync(path.join(repo,'tests/integrations/dsh/fixtures/packet10-rejected-terminal.json'),'utf8') :
        JSON.stringify({schema_version:'WriterTaskResultV1',result:{outcome:'blocked',reason:'isolated L01 adapter calibration',recovery_action:'separate authorized live'}});
      const events=failureFixture==='provider-error' && bodyChunks.length>1 ? [
        {choices:[{index:0,delta:{role:'assistant',reasoning:'The request is being processed.'},finish_reason:null}]},
        {error:{message:'Controlled provider stream failure',type:'InternalServerError',code:500}}]
        : [{choices:[{index:0,delta:{role:'assistant',tool_calls:[{index:0,id:'l01-fake',type:'function',function:{name:'c2p_terminal',arguments:args}}]},finish_reason:null}]},
          {choices:[{index:0,delta:{},finish_reason:'tool_calls'}],usage:{prompt_tokens:17,completion_tokens:11}}];
      if(failureFixture==='stream-finalization' && bodyChunks.length>1)events.push({choices:[],usage:{prompt_tokens:17,completion_tokens:11}});
      response.writeHead(200,{'content-type':'text/event-stream'});response.end(events.map(x=>'data: '+JSON.stringify(x)+'\n\n').join('')+'data: [DONE]\n\n');
    });});
    await new Promise(resolve=>server.listen(8006,'127.0.0.1',resolve));
  }
  const loaded=loadProfileDirectory('l01',profileDir,path.join(runtime,'node_modules/@deepseek-ai/dsh/package.json'));
  ctx=await boot('l01',config,[...loaded.layers.flatMap(x=>x.patches),...loaded.patches,
    ...loadOverlayPatches('l01',path.join(pkg,'dev/offline.patch.yml')),...loadOverlayPatches('l01',overlay)],host=>{
      provideCmdline(host,{args:['--host','127.0.0.1','--port','0','--no-open'],exit:()=>{}});
      host.on('llm/stream',(request,next)=>{loopRequests.push(request);return next();});
  });
  kernel=kernelApi.startKernelWorker(ctx,{pythonExecutable:launcher,engineRoot:repo,bootstrapPath:descriptor.bootstrap});
  await kernel.call('initialize',descriptor.initialize);
  const register=ctx.llm.registerAdapter.bind(ctx.llm);let registration;
  ctx.llm.registerAdapter=(providers,adapter)=>{native=adapter;registration=register(providers,adapter);return registration;};
  try{await ctx.plugin(PiAi,profile.provider_config);}finally{ctx.llm.registerAdapter=register;}
  assert.ok(registration);
  if(mode==='live'){
    const prepared=JSON.parse(readFileSync(path.join(output,'calibration.json'),'utf8'));
    projection=await makeProjection(prepared.binding,prepared.loop,readFileSync(wirePath,'utf8'));
    const budget=py('--action',{action:'budget',path:path.join(taskRoot,'run/artifacts/06_authoring/invocations')});
    assert.equal(budget.call_count,0);assert.equal(budget.pending_input_tokens,0);assert.equal(budget.spent_input_tokens,0);
    save('live-started.json',{at:new Date().toISOString(),authorization:bindFile(authorizationPath),tokenizer:bindFile(tokenPath),inference_requests:0});
    registration();observeFetch();
    monitor=setInterval(async()=>{
      if(metricsInflight)return;metricsInflight=true;
      try{
        const res=await originalFetch('http://127.0.0.1:8006/metrics',{signal:AbortSignal.timeout(5000)});
        assert.equal(res.status,200);const raw=await res.text();assert.ok(raw.length<2<<20);
        const observations=raw.split('\n').filter(x=>!x.startsWith('#') && /num_requests_running|num_requests_waiting|kv_cache_usage_perc|gpu_cache_usage_perc/.test(x));
        save('runtime-monitor-latest.json',{at:new Date().toISOString(),observations});
        for(const row of observations){const value=Number(row.trim().split(/\s+/).at(-1));
          if((/num_requests_running/.test(row)&&value>1)||(/num_requests_waiting/.test(row)&&value>0)||(/cache_usage_perc/.test(row)&&value>=0.9))throw new Error('l01_runtime_pressure');
        }
      }catch(error){pressureStop.abort(error);}finally{metricsInflight=false;}
    },10000);
  }else{
    const calibrator=await ctx.agents.create({sessionId:'l01-calibrator',setup:agentCtx=>{
      writer.installNativeWriter(agentCtx,descriptor.input);agentCtx.on('agent/pre-step',(request,next)=>request.step>1?Promise.resolve({kind:'reject'}):next());
    }});
    let binding;
    try{binding=await writer.renderWriterInput(calibrator.agent,descriptor.input);
      calibrator.agent.followup(createUserMessage({content:[{type:'text',text:descriptor.input.task_view_json}],source:{kind:'user'}}));
      await calibrator.agent.whenIdle();await ctx.sessionPersistence.flush();
    }finally{await calibrator.dispose();registration();}
    assert.equal(bodyChunks.length,1);assert.equal(loopRequests.length,1);
    const wire=bodyChunks[0],body=JSON.parse(wire);
    assert.equal(body.model,profile.model);assert.equal(body.max_tokens,4096);assert.equal(body.temperature,0.6);
    const provider=profile.provider_config.providers.openai;
    assert.equal(descriptor.model.options.reasoningEffort,provider.reasoning,'frozen worker mode');
    assert.equal(descriptor.profile.thinking_token_reserve,1024,'unchanged Formalizer reserve');
    assert.equal(descriptor.model.writer_thinking_tokens,descriptor.writer_thinking_tokens);
    assert.equal(JSON.parse(readFileSync(descriptor.bootstrap,'utf8')).composition_spec.effective_config.writer_thinking_tokens,
      descriptor.writer_thinking_tokens,'bound Writer measurement reserve');
    if(provider.reasoning==='off'){
      assert.equal(provider.compat.thinkingFormat,'chat-template');
      assert.deepEqual(provider.compat.chatTemplateKwargs,{enable_thinking:false});
      assert.equal(Object.hasOwn(provider,'thinkingBudgets'),false);
      assert.deepEqual(body.chat_template_kwargs,{enable_thinking:false});
      assert.equal(Object.hasOwn(body,'reasoning_effort'),false);
      assert.equal(Object.hasOwn(body,'thinking_token_budget'),false);
      assert.equal(descriptor.writer_thinking_tokens,0);
    }else{
      assert.equal(provider.reasoning,'low','only frozen low/off modes');
      assert.equal(body.reasoning_effort,'low');
      assert.equal(body.thinking_token_budget,provider.thinkingBudgets.low);
      assert.equal(descriptor.writer_thinking_tokens,provider.thinkingBudgets.low);
      assert.equal(Object.hasOwn(body,'chat_template_kwargs'),false);
    }
    assert.deepEqual(body.tool_choice,provider.toolChoice,'frozen native selection');
    assert.equal(provider.compat.supportsStrictMode,false,'omit SDK parameter-schema opt-out');
    assert.equal(body.tools.length,1);
    assert.equal(Object.hasOwn(body.tools[0].function,'strict'),false,'server-default parameter schema must not be opted out');
    assert.equal(Object.hasOwn(body,'top_p'),false);assert.equal(Object.hasOwn(body,'top_k'),false);
    writeFileSync(wirePath,wire);
    const loop=JSON.parse(JSON.stringify(loopRequests[0],(key,value)=>key==='signal'?undefined:value));
    save('calibration.json',{binding,loop,actual_provider_body:bindFile(wirePath),calibration_sends:1,
      network:'isolated loopback fake only',qwen_tokens_measured:false,unsupported_sampling_fields:['top_p','top_k']});
    writeFileSync(tokenPath,JSON.stringify({schema_version:'L01TokenizerReceiptV1',origin:'isolated_offline_placeholder',
      model:profile.model,base_url:profile.base_url,meter_version:'vllm-exact-dsh-wire-receipt/2',wire_digest:sha(wire),
      input_tokens:Math.ceil(Buffer.byteLength(wire)/4),parent_namespace:JSON.parse(process.env.C2P_L01_PARENT_NETNS)}));
    projection=await makeProjection(binding,loop,wire);
    if(mode==='prepare'){
      const engine=JSON.parse(readFileSync(descriptor.bootstrap,'utf8')).composition.engine_digest;
      packet={schema_version:'L01ExecutionPacketV1',engine_digest:engine,candidate,profile,
        descriptor_path:path.join(output,'descriptor.json'),calibration_path:path.join(output,'calibration.json'),
        inference_requests:0,scope:'one synthetic B01 scalar Writer page; transport/parser/local receipt only',
        frozen_files:[...new Set([profilePath,worker,fileURLToPath(import.meta.url),config,overlay,launcher,descriptor.bootstrap,
          path.join(output,'descriptor.json'),path.join(output,'calibration.json'),wirePath])].map(bindFile),
        stop_conditions:['nonidle queue/cache pressure','model/source/composition/wire drift','token cap/deadline',
          'missing usage/finish/terminal','content/authority/binding rejection','unknown send: retain reservation, no resend'],
        live_authorized:false,actual_model_tokenizer:'pending authorized non-generating /tokenize; includes messages+tools',
        admission:'current original full offline certificate plus separately concrete operator authorization required'};
      save('packet.json',packet);
      console.log(JSON.stringify({status:'offline_packet_prepared',packet:path.join(output,'packet.json'),packet_digest:sha(readFileSync(path.join(output,'packet.json'))),inference_requests:0}));
    }else{bodyChunks=[];observeFetch();}
  }
  if(mode!=='prepare'){
    const result=await execute();save('result.json',{receipt:result,request_count:sends,provider:streamFacts,
      original_budget:py('--action',{action:'budget',path:path.join(taskRoot,'run/artifacts/06_authoring/invocations')}),
      actual_model_inference_requests:mode==='live'?sends:0});
    console.log(JSON.stringify({status:mode==='live'?'live_complete':'offline_native_complete',receipt:result,requests:sends}));
  }
}catch(error){operationFailure=error;save('failure.json',{...(streamFailure??{type:error.constructor.name,message:error.message}),
  secondary_failure:streamFailure?{type:error.constructor.name,message:error.message}:null,
  cleanup_failures:error.cleanupFailures??[],
  terminal_observation:error.terminalObservation??null,
  request_counts:{primary:mode==='live'?sends:0,isolated_offline:mode==='live'?0:sends,
    tokenize:mode==='live' && existsSync(tokenPath)?1:0,auxiliary:0},
  actual_model_inference_requests:mode==='live'?sends:0,
  reservation_policy:'original reducer; unknown held, no repeat',stage:'L01'});throw error;
}finally{
  clearInterval(monitor);globalThis.fetch=originalFetch;
  const errors=[];
  for(const cleanup of [async()=>{if(kernel){await kernel.close();workerClosed=true;}},()=>ctx?.sessionPersistence.flush(),()=>ctx?.fiber.dispose(),
    async()=>{if(server){server.closeAllConnections();await new Promise((resolve,reject)=>server.close(e=>e?reject(e):resolve()));}}]){
    try{await cleanup();}catch(error){errors.push(error.message);}
  }
  let readback;
  if(descriptor){
    try{readback=py('--action',{action:'snapshot',bootstrap:descriptor.bootstrap});save('owner-readback.json',readback);}
    catch(error){errors.push('owner_readback_failed:'+error.message);}
  }
  const sentinel=existsSync(path.join(taskRoot,'python-sentinel.json'))?JSON.parse(readFileSync(path.join(taskRoot,'python-sentinel.json'),'utf8')):null;
  if(workerClosed && (!sentinel || sentinel.state!=='closed' || sentinel.probe_refused!==true || sentinel.model_calls!==0 || sentinel.network_calls!==0))errors.push('python_refusal_sentinel_unverified');
  save('cleanup.json',{worker_scope_quiescent:workerClosed,sentinel,errors,
    remote_provider_quiescence:mode==='live'?(readback?.task?.provider_quiescence?'owner observation registered':'unproven'): 'own isolated fake closed'});
  save('layered-outcome.json',{request_counts:{primary:mode==='live'?sends:0,isolated_offline:mode==='live'?0:sends,
    tokenize:mode==='live' && existsSync(tokenPath)?1:0,auxiliary:0},
    provider:{http_status:streamFacts?.http_status??null,finish_reasons:streamFacts?.finish_reasons??null,
      usage:streamFacts?.usage??null,
      native_completion_registered:readback?.task?.provider_quiescence!=null},
    fees:{spent_input_tokens:readback?.budget?.spent_input_tokens??null,
      pending_input_tokens:readback?.budget?.pending_input_tokens??null},
    task:readback?.task?.state??null,backend:readback?.backend?.state??null,
    domain_receipt:readback?.task?.receipt??null,
    primary_failure:streamFailure?.message??operationFailure?.message??null,
    cleanup_failures:[...(operationFailure?.cleanupFailures??[]),...errors.map(message=>({stage:'l01.cleanup',message}))]});
  if(errors.length){
    if(operationFailure){
      operationFailure.cleanupFailures??=[];
      operationFailure.cleanupFailures.push(...errors.map(message=>({stage:'l01.cleanup',message})));
      const failure=JSON.parse(readFileSync(path.join(output,'failure.json'),'utf8'));
      save('failure.json',{...failure,cleanup_failures:operationFailure.cleanupFailures});
      throw operationFailure;
    }
    throw new Error('l01_cleanup_failed:'+errors.join(','));
  }
}
