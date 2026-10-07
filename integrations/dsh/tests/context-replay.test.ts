/** Actual DSH Session replacement/replay. Full loop integration is separate. */
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { test } from 'node:test';
import { createUserMessage } from '@deepseek-ai/dsh-llm';
import { Session, SessionId } from '@deepseek-ai/dsh-session';
import type * as PolicyApi from '../src/context-policy.js';

const staged = path.join(process.env.C2P_DSH_DEV_ROOT!, 'home/profiles/node_modules/@code2paper/dsh-bundle');
const api = await import(pathToFileURL(path.join(staged,'lib/context-policy.js')).href) as typeof PolicyApi;
const digest = (text:string):string => `sha256:${createHash('sha256').update(text,'utf8').digest('hex')}`;
const scope: PolicyApi.MaterialScope = { executionId:'run:context',taskId:'task:writer',sessionId:'session:writer',epoch:1,revision:3,snapshotDigest:digest('frozen') };
const materials: PolicyApi.RequiredMaterial[] = [
  {id:'author:1',kind:'author_surface',text:'Original author scope and limitation.',bytesDigest:digest('Original author scope and limitation.')},
  {id:'span:1',kind:'exact_excerpt',text:'return factor * input\n',bytesDigest:digest('return factor * input\n')},
  {id:'occurrence:1',kind:'occurrence',text:'Frozen occurrence binding, revision 3.',bytesDigest:digest('Frozen occurrence binding, revision 3.')},
  {id:'formula:1',kind:'formula',text:'[[FORMULA:frozen-package]]',bytesDigest:digest('[[FORMULA:frozen-package]]')},
];

test('actual replacement drops original materials; summary cannot satisfy them; restored surface survives seed replay',()=>{
  const policy = new api.MaterialRestoration(scope,materials);
  const session = Session.create(SessionId(scope.sessionId));
  const initial = policy.restore(session,scope);
  assert.equal(initial.length,4);
  assert.equal(policy.restore(session,scope).length,0);
  policy.assertRequest(session.deriveMessages(),scope);
  const nodes = session.surface.nodes;
  assert.equal(nodes.length,4);
  const summary = createUserMessage({source:{kind:'user'},content:[{type:'text',text:materials.map(row=>row.text).join('\n')}]});
  const replacement = session.append('user/message',summary,{surfaceOp:{op:'replace',startSeq:nodes[0]!,endSeq:nodes[3]!},sourceEventSeqs:[...nodes]});
  assert.equal(policy.missing(session.deriveMessages()).length,4);
  assert.throws(()=>policy.assertRequest(session.deriveMessages(),scope),/material_restoration_required/);
  const restored = policy.restore(session,scope);
  assert.equal(restored.length,4);
  policy.assertRequest(session.deriveMessages(),scope);
  const replay = Session.create(session.id,[...initial,replacement,...restored]);
  policy.assertRequest(replay.deriveMessages(),scope);
  assert.equal(policy.restore(replay,scope).length,0);
});

test('cross-session/revision and rewritten bytes are refused',()=>{
  const policy = new api.MaterialRestoration(scope,materials);
  assert.throws(()=>policy.restore(Session.create(SessionId('session:other')),scope),/material_session_invalid/);
  assert.throws(()=>policy.restore(Session.create(SessionId(scope.sessionId)),{...scope,revision:4}),/material_scope_stale/);
  assert.throws(()=>new api.MaterialRestoration(scope,[{...materials[0]!,text:'Rewritten author intent'}]),/material_binding_invalid/);
  assert.throws(()=>new api.MaterialRestoration(scope,[materials[0]!,materials[0]!]),/material_binding_invalid/);
  const requestOnly=materials.map(material=>({role:'user' as const,content:[{type:'text' as const,text:material.text}]}));
  assert.throws(()=>policy.assertRequest(requestOnly,scope),/material_restoration_required/);
});
