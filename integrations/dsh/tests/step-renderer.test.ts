/** Actual SDK serialization at a receiver which cannot generate model output. */
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { test } from 'node:test';
import { createSystemMessage,createUserMessage,createAssistantMessage,createToolResultMessage,ToolCallId,
  type GenerateOptions } from '@deepseek-ai/dsh-llm';
import type * as RendererApi from '../src/step-renderer.js';
import type * as ToolApi from '../src/task-tools.js';
import type { JsonObject } from '../src/wire.js';

const staged=path.join(process.env.C2P_DSH_DEV_ROOT!,'home/profiles/node_modules/@code2paper/dsh-bundle/lib/step-renderer.js');
const api=await import(pathToFileURL(staged).href) as typeof RendererApi;

test('actual SDK registered read parameters equal the Kernel V2 wire gate',async()=>{
  const tools=await import(pathToFileURL(path.join(path.dirname(staged),'task-tools.js')).href) as typeof ToolApi;
  const repo=path.resolve(import.meta.dirname,'../../..');
  const output=execFileSync(path.join(process.env.C2P_DSH_DEV_ROOT!,'pyworker/bin/python'),['-c',
    'import json; from code2paper.integrations.dsh.step_admission import READ_TOOL; print(json.dumps(READ_TOOL["parameters"]))'],
    {cwd:repo,env:{...process.env,PYTHONPATH:path.join(repo,'src'),PYTHONDONTWRITEBYTECODE:'1'},encoding:'utf8'});
  let reads=0;
  const tool=tools.createScopedReadTool({sessionId:'test:read',read:async()=>{reads++;throw new Error('unexpected read');},stop:async()=>{}});
  assert.deepEqual(tool.parameters,JSON.parse(output));
  await assert.rejects(tool.execute({grant_id:'opaque',offset:0,length:1,path:'/foreign'},{} as never),/invalid arguments/);
  assert.equal(reads,0);
});

test('fresh actual SDK wire contains changed native tool history; original endpoint receives zero requests',async()=>{
  let originalArrivals=0;
  const original=createServer((_request,response)=>{originalArrivals++;response.writeHead(500);response.end();});
  await new Promise<void>(resolve=>original.listen(0,'127.0.0.1',resolve));
  try {
    const address=original.address();assert.ok(address && typeof address!=='string');
    const config:JsonObject={providers:{openai:{api:'openai-completions',baseURL:`http://127.0.0.1:${address.port}/v1`,
      models:[{id:'c2p-render-fixture',contextWindow:131072,maxTokens:4096,input:['text'],reasoningEfforts:false}],
      compat:{supportsStore:false,supportsDeveloperRole:false,maxTokensField:'max_tokens'},
      toolChoice:'required',retryPolicy:{mode:'normal',maxRetries:0}}}};
    const request:GenerateOptions={provider:'openai',model:'c2p-render-fixture',maxTokens:4096,temperature:0,
      messages:[createSystemMessage('Frozen system: Ω.'),createUserMessage({source:{kind:'user'},content:[{type:'text',text:'原始 TaskView。'}]})],
      tools:[{name:'c2p_read',description:'Bounded navigation.',parameters:{type:'object',properties:{grant_id:{type:'string'}},required:['grant_id'],additionalProperties:false}}]};
    const first=await api.observeLocalWriterWire(config,request);
    assert.equal(first.model,request.model);assert.equal(first.max_tokens,4096);assert.equal(first.tool_choice,'required');
    assert.deepEqual(first.messages,[{role:'system',content:'Frozen system: Ω.'},{role:'user',content:'原始 TaskView。'}]);
    const callId=ToolCallId('call_render_read');
    const second=await api.observeLocalWriterWire(config,{...request,messages:[...request.messages,
      createAssistantMessage({source:{provider:request.provider,model:request.model},
        content:[{type:'tool-call',id:callId,name:'c2p_read',arguments:'{"grant_id":"explicit"}'}]}),
      createToolResultMessage({callId,isError:false,content:[{type:'text',text:'Navigation from original issued grant.'}]})]});
    assert.notDeepEqual(second.messages,first.messages);
    const messages=second.messages as JsonObject[];
    assert.equal(messages.length,4);
    assert.equal(messages[2]!.role,'assistant');assert.equal(messages[3]!.role,'tool');
    assert.equal(messages[3]!.tool_call_id,callId);
    assert.equal(messages[3]!.content,'Navigation from original issued grant.');
    assert.equal(originalArrivals,0,'neither rendering operation can address the original endpoint');
  } finally {original.closeAllConnections();await new Promise<void>(resolve=>original.close(()=>resolve()));}
});

test('foreign endpoint and implicit retry profiles refuse without rendering',async()=>{
  const request:GenerateOptions={provider:'openai',model:'fixture',messages:[]};
  for(const profile of [{baseURL:'https://example.invalid/v1',retryPolicy:{mode:'normal',maxRetries:0}},
    {baseURL:'http://127.0.0.1:8006/v1',retryPolicy:{mode:'normal',maxRetries:1}}]) {
    await assert.rejects(api.observeLocalWriterWire({providers:{openai:profile}},request),/step_render_(local_profile_required|profile_invalid)/);
  }
});
