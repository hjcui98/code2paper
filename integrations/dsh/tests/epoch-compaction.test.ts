/** Real SDK compaction transaction and Session replay; no model transport.
 * The auxiliary authority below is explicitly a settled-receipt stand-in.
 * These tests do not claim an actual bound child or ledger settlement.
 */
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { test } from 'node:test';
import { Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import { Session, SessionId, SessionLogOffset } from '@deepseek-ai/dsh-session';
import { SessionProjectionRegistry } from '@deepseek-ai/dsh-session-projection';
import { TokenMeter } from '@deepseek-ai/dsh-token-meter';
import type * as CompactionApi from '../src/epoch-compaction.js';
import type * as PolicyApi from '../src/context-policy.js';

const staged=path.join(process.env.C2P_DSH_DEV_ROOT!,'home/profiles/node_modules/@code2paper/dsh-bundle/lib');
const api=await import(pathToFileURL(path.join(staged,'epoch-compaction.js')).href) as typeof CompactionApi;
const policyApi=await import(pathToFileURL(path.join(staged,'context-policy.js')).href) as typeof PolicyApi;
const digest=(text:string):string=>`sha256:${createHash('sha256').update(text).digest('hex')}`;

function fixture() {
  const ctx=new Context();
  new SessionProjectionRegistry(ctx);
  new TokenMeter(ctx);
  const session=Session.create(SessionId('session:epoch-writer'));
  const text='Frozen full author, exact source, occurrence, and formula material. '.repeat(120);
  const scope:PolicyApi.MaterialScope={executionId:'execution:epoch',taskId:'task:writer',sessionId:String(session.id),
    epoch:1,revision:1,snapshotDigest:digest('source')};
  const policy=new policyApi.MaterialRestoration(scope,[{id:'writer-task-view',kind:'writer_task_view',text,bytesDigest:digest(text)}]);
  const originals=policy.restore(session,scope);
  session.append('turn/start',{turn:1});
  // Compaction's public context uses only session and route here. This fixture
  // is not a started Agent loop or an auxiliary model-generation fixture.
  const parent={session,options:{provider:'openai',model:'fixture'}} as Agent;
  const receipt:CompactionApi.SettledCompaction={role:'compaction',parentSessionId:String(session.id),
    childSessionId:'session:separate-compaction',requestId:'request:compaction-1',provider:'openai',model:'fixture',
    maxTokens:256,rawOutput:[{type:'text',text:'Derived navigation summary.'}],usage:{inputTokens:100,outputTokens:6},
    naturalExhaustion:true,settlementRef:{media_type:'application/json',bytes_digest:digest('fixture-settlement')}};
  return {ctx,session,parent,policy,scope,originals,receipt};
}

test('actual SDK compactRegion uses separate-child hook, leaves unmarked summary, and original materials restore after replay',async()=>{
  const f=fixture();let calls=0;
  try {
    const engine=new api.EpochCompactionEngine(f.ctx,{summarize:async(input,parent)=>{
      calls++;assert.equal(parent,f.parent);
      assert.equal(input.messages[0]?.content[0]?.type,'text');
      assert.equal(f.policy.missing(input.messages).length,0);
      assert.equal(f.ctx.get('llm'),undefined,'no provider or hidden stream is available');
      return f.receipt;
    }},{auto:false});
    const nodes=f.session.surface.nodes;
    const result=await engine.compactRegion(nodes[0]!,nodes.at(-1)!,f.parent);
    assert.equal(calls,1);
    const events=f.session.snapshotEvents(SessionLogOffset(0));
    assert.equal(events.filter(event=>event.type==='compaction/start').length,1);
    assert.equal(events.filter(event=>event.type==='compaction/end').length,1);
    const summary=f.session.eventAt(result.summarySeq);
    assert.equal(summary?.type,'compaction/summary');
    if(summary?.type!=='compaction/summary')throw new Error('summary missing');
    assert.equal('llmStreamCall' in summary.data,false,'separate child cannot fabricate parent stream marker');
    assert.equal(f.policy.missing(f.session.deriveMessages()).length,1);
    assert.throws(()=>f.policy.assertRequest(f.session.deriveMessages(),f.scope),/material_restoration_required/);
    const restoration=f.policy.restore(f.session,f.scope);assert.equal(restoration.length,1);
    const replay=Session.create(f.session.id,[...events,...restoration]);
    f.policy.assertRequest(replay.deriveMessages(),f.scope);
    assert.equal(f.policy.restore(replay,f.scope).length,0);
  } finally {await f.ctx.fiber.dispose();}
});

for(const damaged of ['same-child','missing-usage','unknown-stream','missing-settlement','wrong-route','cap-overflow'] as const) {
  test(`SDK transaction refuses ${damaged}, preserves original surface and closes its marker`,async()=>{
    const f=fixture();let calls=0;
    try {
      const receipt={...f.receipt};
      if(damaged==='same-child')receipt.childSessionId=receipt.parentSessionId;
      if(damaged==='missing-usage')receipt.usage={inputTokens:0,outputTokens:0};
      if(damaged==='unknown-stream')Object.assign(receipt,{naturalExhaustion:false});
      if(damaged==='missing-settlement')receipt.settlementRef={};
      if(damaged==='wrong-route')receipt.model='other';
      if(damaged==='cap-overflow')receipt.maxTokens=257;
      const engine=new api.EpochCompactionEngine(f.ctx,{summarize:async()=>{calls++;return receipt;}},{auto:false,maxTokens:256});
      const before=[...f.session.surface.nodes];
      await assert.rejects(engine.compactRegion(before[0]!,before.at(-1)!,f.parent),/compaction_settlement_unproven/);
      assert.equal(calls,1);assert.deepEqual(f.session.surface.nodes,before);
      f.policy.assertRequest(f.session.deriveMessages(),f.scope);
      const events=f.session.snapshotEvents(SessionLogOffset(0));
      assert.equal(events.filter(event=>event.type==='compaction/end').length,1);
      assert.equal(events.filter(event=>event.type==='compaction/summary').length,0);
    } finally {await f.ctx.fiber.dispose();}
  });
}

test('cached input remains observed usage on the actual SDK checkpoint',async()=>{
  const f=fixture();
  try {
    const receipt={...f.receipt,usage:{inputTokens:0,cacheReadTokens:100,outputTokens:6}};
    const engine=new api.EpochCompactionEngine(f.ctx,{summarize:async()=>receipt},{auto:false,maxTokens:256});
    const nodes=f.session.surface.nodes;
    const result=await engine.compactRegion(nodes[0]!,nodes.at(-1)!,f.parent);
    const summary=f.session.eventAt(result.summarySeq);
    assert.equal(summary?.type,'compaction/summary');
    if(summary?.type!=='compaction/summary')throw new Error('summary missing');
    assert.deepEqual(summary.data.usage,receipt.usage);
    assert.equal('llmStreamCall' in summary.data,false);
  } finally {await f.ctx.fiber.dispose();}
});

test('implicit compaction/overflow retries refuse before creating a service',async()=>{
  const f=fixture();
  try {
    for(const config of [{compactionRetries:1},{maxOverflowRetries:1},
      {modelPolicies:[{provider:'openai',model:'fixture',compactionRetries:1}]}]) {
      assert.throws(()=>new api.EpochCompactionEngine(f.ctx,{summarize:async()=>f.receipt},config),/compaction_implicit_retry_unsupported/);
    }
  } finally {await f.ctx.fiber.dispose();}
});
