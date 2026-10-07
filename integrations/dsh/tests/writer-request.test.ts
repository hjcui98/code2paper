/** C00: real Loader + loop + installed pi-ai adapter, isolated local HTTP/SSE only. */
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdirSync, mkdtempSync, readFileSync, realpathSync, symlinkSync, writeFileSync } from 'node:fs';
import { createServer } from 'node:http';
import type { Server } from 'node:http';
import path from 'node:path';
import { after, before, test } from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { boot, loadOverlayPatches, loadProfileDirectory } from '@deepseek-ai/dsh-app-boot';
import { provideCmdline } from '@deepseek-ai/dsh-cmdline';
import { createUserMessage, isAgentLoopRequest } from '@deepseek-ai/dsh-llm';
import type { GenerateOptions } from '@deepseek-ai/dsh-llm';
import type { Context } from '@deepseek-ai/cordis';
import type { AgentHandle } from '@deepseek-ai/dsh-agent';
import type { SessionId } from '@deepseek-ai/dsh-session';
import type {} from '@deepseek-ai/dsh-session-persistence';
import * as PiAi from '@deepseek-ai/dsh-llm-pi-ai';
import type * as RendererApi from '../src/writer-request.js';
import type * as WireApi from '../src/wire.js';

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const pkg = path.join(repo, 'integrations/dsh');
const devRoot = process.env.C2P_DSH_DEV_ROOT ?? path.join(repo, '.dsh-dev');
const staged = path.join(devRoot, 'home/profiles/node_modules/@code2paper/dsh-bundle');
const runtime = path.join(devRoot, 'runtime');
const python = path.join(devRoot, 'pyworker/bin/python');
const schemaRoot = path.join(pkg, 'wire-v1');
let privateRoot: string;
let ctx: Context;
let renderer: typeof RendererApi;
let wire: typeof WireApi;
let server: Server;
let endpoint: string;
const handles: AgentHandle[] = [];
const httpRequests: { path: string; body: string; sse: string }[] = [];
const requests: GenerateOptions[] = [];
let responseRaw = '';
let responseSequence = 0;
let terminalValue: WireApi.JsonValue | undefined;
let capture: import('../src/terminal-result.js').TerminalArgumentCapture;
let composition: RendererApi.WriterComposition;
let input: RendererApi.WriterInputRefV1;
let inputBytes: Uint8Array;
let evidence: RendererApi.ProjectionEvidence | undefined;
let authority: RendererApi.WriterProjectionAuthority;
let projection: RendererApi.WriterWireProjectionV1;
let preparedSends = 0;

function py(code: string, value?: unknown, args: string[] = [], rawInput?: Uint8Array): string {
  const stdin = rawInput ?? (value === undefined ? undefined : JSON.stringify(value));
  const result = spawnSync(python, ['-c', code, ...args], {
    cwd: repo, input: stdin, encoding: 'utf8', timeout: 60000,
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' }, maxBuffer: 4 << 20,
  });
  if (privateRoot !== undefined) {
    const record = { argv: [python, '-c', code, ...args], cwd: repo, status: result.status,
      input_sha256: stdin === undefined ? null : createHash('sha256').update(stdin).digest('hex'),
      stdout: result.stdout, stderr: result.stderr, error: result.error?.message };
    writeFileSync(path.join(privateRoot, `python-${String(responseSequence++)}.json`), `${JSON.stringify(record, null, 2)}\n`);
  }
  assert.equal(result.error, undefined);
  assert.equal(result.status, 0, result.stderr);
  return result.stdout.trim();
}

const PY_IMPORTS = [
  'import sys,json', 'from pathlib import Path',
  'from code2paper.agentic.digest import canonical_json_bytes,digest_json,digest_bytes',
  'from code2paper.integrations.dsh.protocol import strict_json_loads,parse_model',
  'from code2paper.integrations.dsh import writer_contract as c',
  'from code2paper.integrations.dsh.artifacts import ArtifactStore,TaskScope',
].join('\n');

function schema(name: string): WireApi.JsonObject {
  const value = wire.decodeWire(readFileSync(path.join(schemaRoot, `${name}.schema.json`)));
  assert.ok(wire.isObject(value)); return value;
}

function digest(value: unknown): string { return py(`${PY_IMPORTS}\nprint(digest_json(strict_json_loads(sys.stdin.buffer.read())))`, value); }

function artifact(value: unknown): WireApi.JsonObject {
  return JSON.parse(py(`${PY_IMPORTS}\nstore=ArtifactStore(Path(sys.argv[1]),TaskScope('c00-controlled-execution','c00-controlled-task',0))\nprint(canonical_json_bytes(store.put_json(strict_json_loads(sys.stdin.buffer.read()))).decode())`, value, [privateRoot])) as WireApi.JsonObject;
}

function artifactRaw(raw: string): WireApi.JsonObject {
  return JSON.parse(py(`${PY_IMPORTS}\nstore=ArtifactStore(Path(sys.argv[1]),TaskScope('c00-controlled-execution','c00-controlled-task',0))\nraw=sys.stdin.buffer.read()\nref=store.put(raw,media_type='application/json',semantic_digest=digest_json(strict_json_loads(raw)))\nprint(canonical_json_bytes(ref).decode())`, undefined, [privateRoot], Buffer.from(raw))) as WireApi.JsonObject;
}

function sealInput(value: WireApi.JsonObject): { value: RendererApi.WriterInputRefV1; bytes: Uint8Array } {
  const text = py(`${PY_IMPORTS}\nv=strict_json_loads(sys.stdin.buffer.read());v.pop('input_digest',None)\nv['input_digest']=digest_json(v)\nprint(canonical_json_bytes(parse_model(canonical_json_bytes(v),c.WriterInputRefV1)).decode())`, value);
  return { value: JSON.parse(text) as RendererApi.WriterInputRefV1, bytes: Buffer.from(text) };
}

async function makeInput(cap: number, extra: WireApi.JsonObject = {}): Promise<RendererApi.WriterInputRefV1> {
  const base = { ...input, effective_options: { ...input.effective_options, maxTokens: cap }, post_clamp_max_output_tokens: cap, ...extra };
  return sealInput(base).value;
}

before(async () => {
  privateRoot = mkdtempSync(path.join(process.env.C2P_DSH_RUN_ROOT ?? path.join(devRoot, 'run'), 'stage03-writer-request-'));
  console.log(`C00_EVIDENCE_ROOT=${privateRoot}`);
  mkdirSync(path.join(privateRoot, 'workspace'));
  mkdirSync(path.join(privateRoot, 'node_modules/@code2paper'), { recursive: true });
  symlinkSync(path.join(runtime, 'node_modules/@deepseek-ai'), path.join(privateRoot, 'node_modules/@deepseek-ai'), 'dir');
  symlinkSync(staged, path.join(privateRoot, 'node_modules/@code2paper/dsh-bundle'), 'dir');
  renderer = await import(pathToFileURL(path.join(staged, 'lib/writer-request.js')).href) as typeof RendererApi;
  wire = await import(pathToFileURL(path.join(staged, 'lib/wire.js')).href) as typeof WireApi;
  server = createServer((request, response) => {
    let body = '';
    request.setEncoding('utf8');
    request.on('data', (chunk: string) => { body += chunk; });
    request.on('end', () => {
      const id = `c00-provider-call-${String(httpRequests.length)}`;
      const chunks = [responseRaw.slice(0, Math.floor(responseRaw.length / 2)), responseRaw.slice(Math.floor(responseRaw.length / 2))];
      const events = [
        { choices: [{ index: 0, delta: { role: 'assistant', tool_calls: [{ index: 0, id, type: 'function', function: { name: renderer.WRITER_TERMINAL, arguments: chunks[0] } }] }, finish_reason: null }] },
        { choices: [{ index: 0, delta: { tool_calls: [{ index: 0, function: { arguments: chunks[1] } }] }, finish_reason: null }] },
        { choices: [{ index: 0, delta: {}, finish_reason: 'tool_calls' }], usage: { prompt_tokens: 17, completion_tokens: 11 } },
      ];
      const sse = `${events.map(event => `data: ${JSON.stringify(event)}\n\n`).join('')}data: [DONE]\n\n`;
      httpRequests.push({ path: request.url ?? '', body, sse });
      response.writeHead(200, { 'content-type': 'text/event-stream' }); response.end(sse);
    });
  });
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  const address = server.address(); assert.ok(address !== null && typeof address !== 'string');
  endpoint = `http://127.0.0.1:${String(address.port)}`;
  // This is a fixed fake-service credential generated by this test, never an ambient key.
  process.env['C2P_STAGE03_TEST_ONLY_KEY'] = 'local-fake-service';
  const profileDir = path.join(devRoot, 'home/profiles/code2paper-dev-compat');
  const profile = loadProfileDirectory('c00-writer-test', profileDir, path.join(runtime, 'node_modules/@deepseek-ai/dsh/package.json'));
  mkdirSync(path.join(privateRoot, 'cfg'));
  const config = path.join(privateRoot, 'cfg/cordis.yml');
  writeFileSync(config, readFileSync(path.join(profileDir, 'cordis.yml')));
  const overlay = path.join(privateRoot, 'overlay.yml');
  writeFileSync(overlay, JSON.stringify([{ id: 'session-persistence-jsonl', config: { root: path.join(privateRoot, 'sessions'), compression: 'none' } }]));
  const patches = [...profile.layers.flatMap(layer => layer.patches), ...profile.patches,
    ...loadOverlayPatches('c00-writer-test', path.join(pkg, 'dev/offline.patch.yml')), ...loadOverlayPatches('c00-writer-test', overlay)];
  ctx = await boot('c00-writer-test', config, patches, host => {
    provideCmdline(host, { args: ['--host', '127.0.0.1', '--port', '0', '--no-open'], exit: () => {} });
    host.on('llm/stream', (request, next) => { requests.push(request); return next(); });
    // Every controlled fixture turn has one attempt, including a broken guard.
    host.on('agent/pre-step', (request, next) => request.step > 1 ? Promise.resolve({ kind: 'reject' }) : next());
  });
  await ctx.plugin(PiAi, { providers: { deepseek: { apiKeyEnv: 'C2P_STAGE03_TEST_ONLY_KEY', baseURL: endpoint,
    reasoning: 'off', retryPolicy: { mode: 'normal', maxRetries: 0 } } } });
  const terminal = await import(pathToFileURL(path.join(staged, 'lib/terminal-result.js')).href) as typeof import('../src/terminal-result.js');
  capture = new terminal.TerminalArgumentCapture(); capture.install(ctx);
  const locations = [process.execPath, path.join(staged, 'lib/writer-request.js'), path.join(staged, 'lib/wire.js'),
    path.join(staged, 'lib/index.js'), path.join(staged, 'lib/build-receipt.json'),
    path.join(runtime, 'node_modules/@deepseek-ai/dsh-system-prompt/lib/index.js'),
    path.join(runtime, 'node_modules/@deepseek-ai/dsh-llm-pi-ai/lib/index.js'),
    path.join(runtime, 'node_modules/@deepseek-ai/cordis-plugin-loader/lib/index.js'), path.join(pkg, 'package-lock.json')];
  const files = locations.map(location => ({ path: location, resolvedPath: realpathSync(location), digest: `sha256:${createHash('sha256').update(readFileSync(location)).digest('hex')}` }));
  // This is the C00 DSH portion of composition. C02 adds the actual Python worker/engine/validator.
  const measured = { schema_version: 'C00DshMeasurementV1', files, node_version: process.version, upstream_source_sha: null };
  writeFileSync(path.join(privateRoot, 'dsh-composition.json'), JSON.stringify(measured, null, 2));
  composition = { digest: digest(measured), rendererVersion: renderer.WRITER_RENDERER_VERSION,
    rendererDigest: files[1]!.digest, files, verify: async () => {
      for (const file of files) assert.equal(`sha256:${createHash('sha256').update(readFileSync(file.path)).digest('hex')}`, file.digest);
    } };
  const material = JSON.parse(py(`${PY_IMPORTS}\nfrom dataclasses import asdict\nfrom tests.integrations.dsh.fixtures.completed_formalizer_fixture import build_fixture\nsink={}\nbuild_fixture(material_sink=sink,require_atom_targets=True,evidence_root=Path(sys.argv[1]))\nprint(canonical_json_bytes({'request':asdict(sink['request']),'raw':sink['writer_raw']}).decode())`, undefined, [privateRoot])) as { request: WireApi.JsonObject; raw: string };
  writeFileSync(path.join(privateRoot, 'domain-material.json'), JSON.stringify(material, null, 2));
  responseRaw = JSON.stringify({ schema_version: 'WriterTaskResultV1', result: { outcome: 'draft', draft: JSON.parse(material.raw) } }, null, 2);
  const ref = artifact(material.request);
  const taskSchema = JSON.parse(py(`${PY_IMPORTS}\nnative,enforcement=c.native_terminal_schema(strict_json_loads(sys.stdin.buffer.read()))\nprint(canonical_json_bytes({'native':native,'enforcement':enforcement}).decode())`, material.request)) as {native: WireApi.JsonObject; enforcement: WireApi.JsonValue[]};
  const native = taskSchema.native;
  const enforcement = taskSchema.enforcement;
  assert.ok(wire.isObject(native) && Array.isArray(enforcement));
  const taskView = py(`${PY_IMPORTS}\nprint(canonical_json_bytes(strict_json_loads(sys.stdin.buffer.read())).decode())`, material.request['input_payload']);
  const values: WireApi.JsonObject = {
    schema_version: 'WriterInputRefV1', request_ref: ref, writer_request: material.request, task_view_json: taskView,
    terminal_schema: schema('WriterTaskResultV1'), native_terminal_schema: native, native_schema_enforcement: enforcement,
    terminal_instruction: 'Return exactly one c2p_terminal tool call with WriterTaskResultV1. For draft, keep the original Writer JSON inside result.draft; otherwise use research_required or blocked. Closing prose cannot submit a result.',
    model: 'deepseek-v4-flash', effective_options: { provider: 'deepseek', temperature: 0.2, reasoningEffort: 'off', maxTokens: 2048 },
    post_clamp_max_output_tokens: 2048, composition_digest: composition.digest,
    renderer_version: composition.rendererVersion, renderer_digest: composition.rendererDigest,
  };
  const sealed = sealInput(values); input = sealed.value; inputBytes = sealed.bytes;
  writeFileSync(path.join(privateRoot, 'writer-input.json'), inputBytes);
  authority = {
    agentHost: ctx,
    inputSchema: schema('WriterInputRefV1'), projectionSchema: schema('WriterWireProjectionV1'),
    validateInput: async bytes => Buffer.from(py(`${PY_IMPORTS}\nprint(canonical_json_bytes(parse_model(sys.stdin.buffer.read(),c.WriterInputRefV1)).decode())`, wire.decodeWire(bytes))),
    digestValue: async value => digest(value),
    evidenceFor: async () => { if (evidence === undefined) throw new wire.WireError('wire_evidence_not_ready'); return evidence; },
    sealProjection: async value => Buffer.from(py(`${PY_IMPORTS}\nprint(canonical_json_bytes(c.seal_projection(strict_json_loads(sys.stdin.buffer.read()))).decode())`, value)),
  };
});

after(async () => {
  for (const handle of handles.reverse()) await handle.dispose();
  await ctx?.sessionPersistence.flush();
  await ctx?.fiber.dispose();
  if (server !== undefined) { server.closeAllConnections(); await new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve())); }
  delete process.env['C2P_STAGE03_TEST_ONLY_KEY'];
  if (privateRoot !== undefined) writeFileSync(path.join(privateRoot, 'release.json'), JSON.stringify({
    state: 'closed', server_listening: server?.listening ?? false, handles: handles.length,
    controlled_http_sends: httpRequests.length, prepare_sends: preparedSends, requests: requests.length,
    scope: 'C00 actual DSH measurement; Python full composition/worker in joint C02-C04',
  }, null, 2));
});

test('first prepare without observed wire evidence refuses; no stream or provider send occurs', async () => {
  const sends = httpRequests.length; const attempts = requests.length;
  await assert.rejects(() => ctx.code2paperBridge.prepare_projection(inputBytes, composition, authority), { code: 'wire_evidence_not_ready' });
  preparedSends += httpRequests.length - sends;
  assert.equal(httpRequests.length, sends); assert.equal(requests.length, attempts);
});

test('public assemble, actual loop first request and real pi-ai provider wire preserve full materials/schema/options/cap', async () => {
  terminalValue = undefined;
  const handle = await ctx.agents.create({ sessionId: `c00-writer-${String(process.pid)}` as SessionId,
    meta: { cwd: path.join(privateRoot, 'workspace') },
    agentOptions: { provider: 'deepseek', model: input.model, maxTokens: input.post_clamp_max_output_tokens },
    setup: async (agentCtx) => {
      await ctx.code2paperBridge.mountPreset(agentCtx);
      renderer.installNativeWriter(agentCtx, input, value => { terminalValue = value; });
    } });
  handles.push(handle);
  const binding = await renderer.renderWriterInput(handle.agent, input);
  handle.agent.followup(createUserMessage({ content: [{ type: 'text', text: input.task_view_json }], source: { kind: 'user' } }));
  await handle.agent.whenIdle();
  assert.equal(httpRequests.length, 1, 'only one controlled fake-service request');
  assert.equal(requests.length, 1, 'only one real loop attempt');
  assert.equal(isAgentLoopRequest(requests[0]!), true);
  assert.deepEqual(terminalValue, JSON.parse(responseRaw));
  const observed = httpRequests[0]!;
  assert.equal(observed.path, '/chat/completions');
  const provider = JSON.parse(observed.body) as Record<string, unknown>;
  assert.deepEqual(provider['messages'], [{ role: 'system', content: binding['system_text'] }, { role: 'user', content: binding['user_text'] }]);
  assert.deepEqual(provider['tools'], [{ type: 'function', function: { name: renderer.WRITER_TERMINAL, description: renderer.WRITER_TERMINAL_DESCRIPTION, parameters: input.native_terminal_schema, strict: false } }]);
  assert.equal(provider['model'], input.model); assert.equal(provider['max_tokens'], input.post_clamp_max_output_tokens);
  assert.equal(provider['temperature'], input.effective_options['temperature']);
  assert.deepEqual(provider['thinking'], { type: 'disabled' }); assert.equal(provider['reasoning_effort'], undefined);
  const streamRaw = capture.raw('c00-provider-call-0', { sessionId: handle.agent.session.id });
  assert.ok(streamRaw !== undefined && streamRaw.state === 'captured');
  assert.equal(streamRaw.text, responseRaw); assert.equal(streamRaw.chunks, 2);
  await ctx.sessionPersistence.flush();
  const loopJson = JSON.parse(JSON.stringify(requests[0], (key, value: unknown) => key === 'signal' ? undefined : value));
  writeFileSync(path.join(privateRoot, 'loop-request.json'), JSON.stringify(loopJson, null, 2));
  writeFileSync(path.join(privateRoot, 'provider-request.raw.json'), observed.body);
  writeFileSync(path.join(privateRoot, 'provider-response.raw.sse'), observed.sse);
  writeFileSync(path.join(privateRoot, 'adapter-arguments.raw.json'), streamRaw.text);
  writeFileSync(path.join(privateRoot, 'raw-observation.json'), JSON.stringify(streamRaw, null, 2));
  const providerRef = artifactRaw(observed.body);
  const loopRef = artifactRaw(JSON.stringify(loopJson));
  const comparison = { binding, loop_digest: loopRef['bytes_digest'], provider_digest: providerRef['bytes_digest'] };
  const measuring = { schema_version: 'WriterMeasurementV1', input_digest: input.input_digest, renderer_digest: input.renderer_digest,
    tokenizer_digest: `sha256:${createHash('sha256').update(readFileSync(fileURLToPath(import.meta.url))).digest('hex')}`,
    meter_version: 'controlled-utf8-byte-id/1', measured_input_tokens: [...Buffer.from(observed.body, 'utf8')].length,
    context_tokens: 131072, safety_margin_tokens: 512, thinking_tokens: 0,
    post_clamp_max_output_tokens: input.post_clamp_max_output_tokens, measured_wire_digest: providerRef['bytes_digest'] };
  const wireEvidence = { schema_version: 'WriterWireEquivalenceV1', input_digest: input.input_digest,
    renderer_digest: input.renderer_digest, composition_digest: input.composition_digest, projection_material_digest: digest(binding),
    provider_wire_ref: providerRef, loop_request_ref: loopRef, comparison_ref: artifact(comparison),
    transport_whitelist: ['request_id', 'tool_call_id'] };
  evidence = { binding, measurement_ref: artifact(measuring), wire_equivalence_ref: artifact(wireEvidence) };
  writeFileSync(path.join(privateRoot, 'wire-comparison.json'), JSON.stringify(comparison, null, 2));
  writeFileSync(path.join(privateRoot, 'measurement.json'), JSON.stringify(measuring, null, 2));
  writeFileSync(path.join(privateRoot, 'wire-equivalence.json'), JSON.stringify(wireEvidence, null, 2));
  const sends = httpRequests.length;
  projection = await ctx.code2paperBridge.prepare_projection(inputBytes, composition, authority);
  assert.ok(Object.isFrozen(projection) && Object.isFrozen(projection.effective_options));
  assert.equal(httpRequests.length, sends); preparedSends += httpRequests.length - sends;
  renderer.compareWriterRequest(projection, requests[0]!);
  writeFileSync(path.join(privateRoot, 'projection.json'), JSON.stringify(projection, null, 2));
  writeFileSync(path.join(privateRoot, 'evidence-refs.json'), JSON.stringify(evidence, null, 2));
});

test('seam rejects material/schema/model/options/cap drift without modifying request', () => {
  assert.ok(projection !== undefined);
  const request = requests[0]!;
  const wrongText = request.messages.map((message, index) => index === 1
    ? { ...message, content: [{ type: 'text' as const, text: 'Host replacement prose' }] } : message);
  for (const [changes, code] of [
    [{ maxTokens: projection.post_clamp_max_output_tokens - 1 }, 'writer_cap_mismatch'],
    [{ maxTokens: projection.post_clamp_max_output_tokens + 1 }, 'writer_cap_mismatch'],
    [{ model: 'wrong-model' }, 'writer_model_drift'],
    [{ temperature: 0.9 }, 'writer_options_drift'],
    [{ messages: wrongText }, 'writer_material_drift'],
    [{ tools: [] }, 'writer_tools_drift'],
  ] as [Partial<GenerateOptions>, string][]) assert.throws(() => renderer.compareWriterRequest(projection, { ...request, ...changes }), { code });
  renderer.compareWriterRequest(projection, request);
  assert.equal(httpRequests.length, 1);
});

test('prepare rejects byte/renderer/certificate drift and unsupported options/conversions with zero sends', async () => {
  const sends = httpRequests.length;
  const changed = { ...composition, files: composition.files.map((file, index) => index === 0 ? { ...file, digest: `sha256:${'0'.repeat(64)}` } : file) };
  await assert.rejects(() => renderer.prepare_projection(ctx, inputBytes, changed, authority), { code: 'composition_drift' });
  await assert.rejects(() => renderer.prepare_projection(ctx, inputBytes, { ...composition, rendererDigest: `sha256:${'0'.repeat(64)}` }, authority), { code: 'writer_identity_drift' });
  const capInput = await makeInput(input.post_clamp_max_output_tokens - 1);
  await assert.rejects(() => renderer.prepare_projection(ctx, Buffer.from(JSON.stringify(capInput)), composition, authority), { code: 'wire_evidence_binding_mismatch' });
  const badOptions = sealInput({ ...input, effective_options: { ...input.effective_options, stop: ['end'] } });
  await assert.rejects(() => renderer.prepare_projection(ctx, badOptions.bytes, composition, authority), { code: 'writer_options_unsupported' });
  const dynamicRequest = { ...input.writer_request, images: ['uncovered dynamic attachment'] };
  const dynamic = sealInput({ ...input, writer_request: dynamicRequest, request_ref: artifact(dynamicRequest) });
  await assert.rejects(() => renderer.prepare_projection(ctx, dynamic.bytes, composition, authority), { code: 'writer_content_unsupported' });
  assert.equal(httpRequests.length, sends); preparedSends += httpRequests.length - sends;
});

test('full terminal guard retains native-unexpressed length/union/extra constraints', () => {
  const full = input.terminal_schema;
  for (const value of [
    { result: { outcome: 'blocked', reason: 'gap', recovery_action: 'owner review' } },
    { schema_version: 'wrong', result: { outcome: 'blocked', reason: 'gap', recovery_action: 'owner review' } },
    { schema_version: 'WriterTaskResultV1', result: 'untrusted string' },
    { schema_version: 'WriterTaskResultV1', extra: true, result: { outcome: 'blocked', reason: 'gap', recovery_action: 'owner review' } },
    { schema_version: 'WriterTaskResultV1', result: { outcome: 'blocked', reason: '', recovery_action: 'retry' } },
    { schema_version: 'WriterTaskResultV1', result: { outcome: 'blocked', reason: 'x', recovery_action: '' } },
    { schema_version: 'WriterTaskResultV1', result: { outcome: 'research_required', requests: [] } },
    { schema_version: 'WriterTaskResultV1', result: { outcome: 'accepted' } },
  ] as WireApi.JsonObject[]) assert.throws(() => wire.validateWireSchema(value, full), { code: 'schema_invalid' });
});

test('task-derived native cardinality rejects empty witnesses and malformed extensions', () => {
  renderer.assertNativeWriterSchema(input.native_terminal_schema);
  const value = JSON.parse(responseRaw) as {result: {draft: {paragraphs: {witnesses: unknown[]}[]}}};
  value.result.draft.paragraphs[0]!.witnesses = [];
  assert.throws(() => wire.parseWire(JSON.stringify(value), input.native_terminal_schema), {code:'schema_invalid'});
  // Legacy full parsing remains available, but cannot bypass native emission.
  wire.parseWire(JSON.stringify(value), input.terminal_schema);
  value.result.draft.paragraphs = [];
  assert.throws(() => wire.parseWire(JSON.stringify(value), input.native_terminal_schema), {code:'schema_invalid'});
  for (const minItems of [-1, 1.5, '1', null]) {
    assert.throws(() => renderer.assertNativeWriterSchema({type:'object',properties:{rows:{type:'array',items:{type:'string'},minItems}}}), {code:'writer_native_cardinality_invalid'});
  }
  assert.throws(() => renderer.assertNativeWriterSchema({type:'object',properties:{text:{type:'string',minItems:1}}}), {code:'writer_native_cardinality_invalid'});
  assert.throws(() => renderer.assertNativeWriterSchema({type:'object',properties:{rows:{type:'array',items:{type:'string'},maxItems:1}}}));
});

test('actual raw native tool preserves minItems on provider wire and refuses empty witness completion', async () => {
  const previous = responseRaw;
  const value = JSON.parse(previous) as {result: {draft: {paragraphs: {witnesses: unknown[]}[]}}};
  value.result.draft.paragraphs[0]!.witnesses = [];
  responseRaw = JSON.stringify(value);
  let accepted = false;
  const beforeSends = httpRequests.length;
  const handle = await ctx.agents.create({sessionId:`c00-empty-witness-${String(process.pid)}` as SessionId,
    setup: agentCtx => { renderer.installNativeWriter(agentCtx,input,()=>{accepted=true;}); }});
  handles.push(handle);
  try {
    handle.agent.followup(createUserMessage({content:[{type:'text',text:input.task_view_json}],source:{kind:'user'}}));
    await handle.agent.whenIdle();
    assert.equal(httpRequests.length,beforeSends+1);
    assert.equal(accepted,false);
    const provider = JSON.parse(httpRequests[beforeSends]!.body) as {tools:{function:{parameters:WireApi.JsonObject}}[]};
    assert.deepEqual(provider.tools[0]!.function.parameters,input.native_terminal_schema);
    assert.ok(JSON.stringify(provider.tools[0]!.function.parameters).includes('"minItems":1'));
    const events = handle.agent.session.snapshotEvents(0 as never);
    const result = events.find(event=>event.type === 'tool/result');
    assert.ok(result !== undefined && result.type === 'tool/result');
    assert.equal(result.data.message.isError,true);
    assert.ok(JSON.stringify(result.data).includes('schema_invalid'));
  } finally { responseRaw = previous; }
});

test('legal new cap requires fresh actual loop/provider evidence and produces a new sealed projection without prepare send', async () => {
  const nextInput = await makeInput(1024);
  const handle = await ctx.agents.create({ sessionId: `c00-reproject-${String(process.pid)}` as SessionId,
    agentOptions: { provider: 'deepseek', model: nextInput.model, maxTokens: 1024 },
    setup: agentCtx => { renderer.installNativeWriter(agentCtx, nextInput); } });
  handles.push(handle);
  const binding = await renderer.renderWriterInput(handle.agent, nextInput);
  const oldRequests = requests.length; const oldSends = httpRequests.length;
  handle.agent.followup(createUserMessage({ content: [{ type: 'text', text: nextInput.task_view_json }], source: { kind: 'user' } }));
  await handle.agent.whenIdle();
  assert.equal(httpRequests.length, oldSends + 1); assert.equal(requests.length, oldRequests + 1);
  const providerRaw = httpRequests[oldSends]!.body;
  assert.equal(JSON.parse(providerRaw)['max_tokens'], 1024);
  const loopRaw = JSON.stringify(requests[oldRequests], (key, value: unknown) => key === 'signal' ? undefined : value);
  const providerRef = artifactRaw(providerRaw); const loopRef = artifactRaw(loopRaw);
  const comparison = { binding, provider_digest: providerRef['bytes_digest'], loop_digest: loopRef['bytes_digest'] };
  const measurement = { schema_version: 'WriterMeasurementV1', input_digest: nextInput.input_digest,
    renderer_digest: nextInput.renderer_digest, tokenizer_digest: `sha256:${createHash('sha256').update(readFileSync(fileURLToPath(import.meta.url))).digest('hex')}`,
    meter_version: 'controlled-utf8-byte-id/1', measured_input_tokens: [...Buffer.from(providerRaw)].length,
    context_tokens: 131072, safety_margin_tokens: 512, thinking_tokens: 0, post_clamp_max_output_tokens: 1024,
    measured_wire_digest: providerRef['bytes_digest'] };
  const equivalence = { schema_version: 'WriterWireEquivalenceV1', input_digest: nextInput.input_digest,
    renderer_digest: nextInput.renderer_digest, composition_digest: nextInput.composition_digest,
    projection_material_digest: digest(binding), provider_wire_ref: providerRef, loop_request_ref: loopRef,
    comparison_ref: artifact(comparison), transport_whitelist: ['request_id', 'tool_call_id'] };
  evidence = { binding, measurement_ref: artifact(measurement), wire_equivalence_ref: artifact(equivalence) };
  const sends = httpRequests.length;
  const nextProjection = await ctx.code2paperBridge.prepare_projection(Buffer.from(JSON.stringify(nextInput)), composition, authority);
  assert.equal(httpRequests.length, sends); preparedSends += httpRequests.length - sends;
  assert.notEqual(nextProjection.input_digest, projection.input_digest);
  assert.notEqual(nextProjection.projection_digest, projection.projection_digest);
  assert.notDeepEqual(nextProjection.measurement_ref, projection.measurement_ref);
  renderer.compareWriterRequest(nextProjection, requests[oldRequests]!);
  assert.throws(() => renderer.compareWriterRequest(projection, requests[oldRequests]!), { code: 'writer_cap_mismatch' });
  mkdirSync(path.join(privateRoot, 'new-cap'));
  for (const [name, bytes] of [['writer-input.json', JSON.stringify(nextInput)], ['projection.json', JSON.stringify(nextProjection)],
    ['provider-request.raw.json', providerRaw], ['loop-request.raw.json', loopRaw], ['evidence.json', JSON.stringify(evidence)]]) {
    writeFileSync(path.join(privateRoot, 'new-cap', name!), bytes!);
  }
});

test('actual native terminal execution refuses an unexpressed minLength; no accepted callback or second provider call', async () => {
  const previous = responseRaw;
  responseRaw = JSON.stringify({ schema_version: 'WriterTaskResultV1', result: { outcome: 'blocked', reason: '', recovery_action: 'retry' } });
  let accepted = false;
  const beforeRequests = requests.length; const beforeSends = httpRequests.length;
  const handle = await ctx.agents.create({ sessionId: `c00-bad-terminal-${String(process.pid)}` as SessionId,
    agentOptions: { provider: 'deepseek', model: input.model, maxTokens: input.post_clamp_max_output_tokens },
    setup: agentCtx => {
      renderer.installNativeWriter(agentCtx, input, () => { accepted = true; });
      // Explicit bounded fixture policy: do not ask the fake service to repair this invalid candidate.
      agentCtx.on('agent/pre-step', (request, next) => request.step > 1 ? Promise.resolve({ kind: 'reject' }) : next());
    } });
  handles.push(handle);
  try {
    handle.agent.followup(createUserMessage({ content: [{ type: 'text', text: input.task_view_json }], source: { kind: 'user' } }));
    await handle.agent.whenIdle();
    assert.equal(httpRequests.length, beforeSends + 1); assert.equal(requests.length, beforeRequests + 1);
    assert.equal(accepted, false);
    const events = handle.agent.session.snapshotEvents(0 as never);
    const result = events.find(event => event.type === 'tool/result');
    assert.ok(result !== undefined && result.type === 'tool/result');
    assert.equal(result.data.message.isError, true);
    assert.ok(JSON.stringify(result.data).includes('schema_invalid'));
    writeFileSync(path.join(privateRoot, 'invalid-terminal-session.json'), JSON.stringify(events, null, 2));
  } finally { responseRaw = previous; }
});

test('actual terminal validates captured raw bytes before native JSON normalization can erase duplicate keys', async () => {
  const previous = responseRaw;
  responseRaw = '{"schema_version":"WriterTaskResultV1","result":{"outcome":"blocked","reason":"first","reason":"last"}}';
  const beforeSends = httpRequests.length; const beforeRequests = requests.length;
  let accepted = false;
  const handle = await ctx.agents.create({ sessionId: `c00-raw-duplicate-${handles.length}` as SessionId,
    agentOptions: { provider: 'deepseek', model: input.model, maxTokens: input.post_clamp_max_output_tokens },
    setup: agentCtx => {
      renderer.installNativeWriter(agentCtx, input, () => { accepted = true; });
      agentCtx.on('agent/pre-step', (request, next) => request.step > 1 ? Promise.resolve({ kind: 'reject' }) : next());
    } });
  handles.push(handle);
  try {
    handle.agent.followup(createUserMessage({ content: [{ type: 'text', text: input.task_view_json }], source: { kind: 'user' } }));
    await handle.agent.whenIdle();
    assert.equal(httpRequests.length, beforeSends + 1); assert.equal(requests.length, beforeRequests + 1);
    assert.equal(accepted, false);
    const events = handle.agent.session.snapshotEvents(0 as never);
    const result = events.find(event => event.type === 'tool/result');
    assert.ok(result !== undefined && result.type === 'tool/result');
    assert.equal(result.data.message.isError, true);
    assert.ok(JSON.stringify(result.data).includes('duplicate_json_key'));
    writeFileSync(path.join(privateRoot, 'duplicate-terminal-session.json'), JSON.stringify(events, null, 2));
  } finally { responseRaw = previous; }
});

const unicodeTerminalCases = [
  { name: 'ascii', reason: 'plain text', expected: 'ok' },
  { name: 'cjk', reason: '正文', expected: 'ok' },
  { name: 'nel', reason: '\u0085', expected: 'schema_invalid' },
  { name: 'bom', reason: '\ufeff', expected: 'ok' },
  { name: 'nbsp', reason: '\u00a0', expected: 'schema_invalid' },
  { name: 'line-separator', reason: '\u2028', expected: 'schema_invalid' },
  { name: 'paragraph-separator', reason: '\u2029', expected: 'schema_invalid' },
  { name: 'ascii-whitespace', reason: ' \t\n', expected: 'schema_invalid' },
  { name: 'whitespace-and-text', reason: '\u0085正文', expected: 'ok' },
  { name: 'non-bmp', reason: '🚀', expected: 'ok' },
  { name: 'max-length', reason: '🚀'.repeat(256), expected: 'ok' },
  { name: 'over-max-length', reason: '🚀'.repeat(257), expected: 'schema_invalid' },
] as const;

for (const sample of unicodeTerminalCases) test(`GC-1 real native terminal Unicode ${sample.name}: ${sample.expected}`, async () => {
  const previous = responseRaw;
  responseRaw = JSON.stringify({ schema_version: 'WriterTaskResultV1', result: { outcome: 'blocked', reason: sample.reason, recovery_action: 'new task' } });
  const beforeSends = httpRequests.length; const beforeRequests = requests.length;
  let accepted: WireApi.JsonValue | undefined;
  const handle = await ctx.agents.create({ sessionId: `gc1-${sample.name}-${handles.length}` as SessionId,
    agentOptions: { provider: 'deepseek', model: input.model, maxTokens: input.post_clamp_max_output_tokens },
    setup: agentCtx => {
      renderer.installNativeWriter(agentCtx, input, value => { accepted = value; });
      // A failed guard is a refusal, not permission for an automatic repair request.
      agentCtx.on('agent/pre-step', (request, next) => request.step > 1 ? Promise.resolve({ kind: 'reject' }) : next());
    } });
  handles.push(handle);
  try {
    handle.agent.followup(createUserMessage({ content: [{ type: 'text', text: input.task_view_json }], source: { kind: 'user' } }));
    await handle.agent.whenIdle();
    assert.equal(httpRequests.length, beforeSends + 1); assert.equal(requests.length, beforeRequests + 1);
    const raw = capture.raw(`c00-provider-call-${beforeSends}`, { sessionId: handle.agent.session.id });
    assert.equal(raw.state, 'captured'); assert.equal(raw.state === 'captured' ? raw.text : null, responseRaw);
    const pythonOutcome = py(`${PY_IMPORTS}\nfrom code2paper.integrations.dsh.protocol import ProtocolError\nraw=sys.stdin.buffer.read()\ntry:\n parse_model(raw,c.WriterTaskResultV1);print('ok')\nexcept ProtocolError as error:\n print(error.code)`, undefined, [], Buffer.from(responseRaw));
    assert.equal(pythonOutcome, sample.expected);
    const events = handle.agent.session.snapshotEvents(0 as never);
    const result = events.find(event => event.type === 'tool/result');
    assert.ok(result !== undefined && result.type === 'tool/result');
    await ctx.sessionPersistence.flush();
    const end = events.find(event => event.type === 'turn/end');
    assert.ok(end !== undefined && end.type === 'turn/end');
    const observed = httpRequests[beforeSends]!;
    for (const [suffix, bytes] of [['provider-request.raw.json', observed.body], ['provider-response.raw.sse', observed.sse],
      ['adapter-arguments.raw.json', responseRaw], ['session.json', JSON.stringify(events)],
      ['result.json', JSON.stringify({ name: sample.name, python: pythonOutcome, callback: accepted !== undefined,
        tool_error: result.data.message.isError, controlled_sends: httpRequests.length - beforeSends, session_id: handle.agent.session.id })]]) {
      writeFileSync(path.join(privateRoot, `gc1-${sample.name}-${suffix}`), bytes!);
    }
    if (sample.expected === 'ok') {
      assert.deepEqual(accepted, JSON.parse(responseRaw));
      assert.equal(result.data.message.isError, false);
      assert.equal(end.data.reason.kind, 'completed');
    } else {
      assert.equal(accepted, undefined);
      assert.equal(result.data.message.isError, true);
      assert.ok(JSON.stringify(result.data).includes('schema_invalid'));
      assert.equal(end.data.reason.kind, 'blocked');
    }
  } finally { responseRaw = previous; }
});
