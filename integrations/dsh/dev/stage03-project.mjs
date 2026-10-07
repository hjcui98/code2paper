/** Trusted Stage03 fixture driver, not the R03 production pump. Run inside the offline launcher. */
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, realpathSync, symlinkSync, writeFileSync } from 'node:fs';
import { createServer } from 'node:http';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const devRoot = process.env.C2P_DSH_DEV_ROOT;
if (devRoot === undefined || process.argv[2] === undefined) throw new Error('candidate environment and trusted driver config required');
const configPath = realpathSync(process.argv[2]);
const cfg = JSON.parse(readFileSync(configPath, 'utf8'));
if (!['observe', 'prepare'].includes(cfg.mode)) throw new Error('unsupported_driver_mode');
const output = realpathSync(cfg.output_root);
const staged = path.join(devRoot, 'home/profiles/node_modules/@code2paper/dsh-bundle');
const runtime = path.join(devRoot, 'runtime');
const python = path.join(devRoot, 'pyworker/bin/python');
const resolver = createRequire(path.join(staged, 'lib/index.js'));
const load = async name => import(pathToFileURL(resolver.resolve(name)).href);
const { boot, loadOverlayPatches, loadProfileDirectory } = await load('@deepseek-ai/dsh-app-boot');
const { provideCmdline } = await load('@deepseek-ai/dsh-cmdline');
const { createUserMessage, isAgentLoopRequest } = await load('@deepseek-ai/dsh-llm');
const { applyChildComposition, childSessionMeta } = await load('@deepseek-ai/dsh-subagent');
const PiAi = await load('@deepseek-ai/dsh-llm-pi-ai');
const renderer = await import(pathToFileURL(path.join(staged, 'lib/writer-request.js')).href);
const wire = await import(pathToFileURL(path.join(staged, 'lib/wire.js')).href);
const terminal = await import(pathToFileURL(path.join(staged, 'lib/terminal-result.js')).href);
const bindingApi = await import(pathToFileURL(path.join(staged, 'lib/session-binding.js')).href);
const bootstrap = JSON.parse(readFileSync(cfg.bootstrap_path, 'utf8'));
const inputBytes = readFileSync(cfg.input_path);
const input = wire.parseWire(inputBytes, wire.decodeWire(readFileSync(path.join(repo, 'integrations/dsh/wire-v1/WriterInputRefV1.schema.json'))));
const imports = [
  'import sys,json', 'from pathlib import Path',
  'from code2paper.agentic.digest import canonical_json_bytes,digest_json,digest_bytes',
  'from code2paper.integrations.dsh.protocol import parse_model,strict_json_loads',
  'from code2paper.integrations.dsh import writer_contract as c',
  'from code2paper.integrations.dsh.artifacts import ArtifactStore,TaskScope',
  'bootstrap=json.loads(Path(sys.argv[1]).read_text())',
].join('\n');
let operation = 0;
function py(code, raw) {
  const result = spawnSync(python, ['-c', `${imports}\n${code}`, cfg.bootstrap_path], {
    input: raw, encoding: 'utf8', cwd: repo, timeout: 120000, maxBuffer: 32 << 20,
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' },
  });
  writeFileSync(path.join(output, `authority-${String(operation++)}.json`), JSON.stringify({
    argv: [python, '-c', `${imports}\n${code}`, cfg.bootstrap_path], cwd: repo,
    input_digest: raw === undefined ? null : `sha256:${createHash('sha256').update(raw).digest('hex')}`,
    status: result.status, signal: result.signal, error: result.error?.message, stdout: result.stdout, stderr: result.stderr,
  }, null, 2), { flag: 'wx' });
  assert.equal(result.error, undefined); assert.equal(result.status, 0, result.stderr);
  return result.stdout.trim();
}
function digest(value) { return py('print(digest_json(strict_json_loads(sys.stdin.buffer.read())))', JSON.stringify(value)); }
function artifact(raw, mediaType = 'application/json') {
  return JSON.parse(py([
    "store=ArtifactStore(Path(bootstrap['artifact_root']),TaskScope(**bootstrap['scope']))",
    'raw=sys.stdin.buffer.read()',
    `ref=store.put(raw,media_type=${JSON.stringify(mediaType)},semantic_digest=digest_json(strict_json_loads(raw)) if ${JSON.stringify(mediaType)} == 'application/json' else None)`,
    'print(canonical_json_bytes(ref).decode())',
  ].join('\n'), raw));
}
const measuredFiles = Object.values(bootstrap.composition.files).map(file => ({ path: file.path, resolvedPath: file.resolved_path, digest: file.digest }));
const composition = {
  digest: bootstrap.composition.composition_digest, rendererVersion: bootstrap.composition.effective_config.renderer_version,
  rendererDigest: bootstrap.composition.files.renderer.digest, files: measuredFiles,
  verify: async () => { py([
    'from code2paper.agentic.authoring_execution_identity import CompositionSpecV1,validate_execution_composition',
    "s=bootstrap['composition_spec']",
    "spec=CompositionSpecV1(files={k:Path(v) for k,v in s['files'].items()},trees={k:Path(v) for k,v in s['trees'].items()},effective_config=s['effective_config'],upstream_source_sha=s.get('upstream_source_sha'))",
    "validate_execution_composition(spec,bootstrap['composition'],engine_root=Path(bootstrap['engine_root']))",
    "print('actual_composition_verified')",
  ].join('\n')); },
};
let evidence = cfg.evidence_path === undefined ? undefined : JSON.parse(readFileSync(cfg.evidence_path, 'utf8'));
const authority = {
  get agentHost() { return ctx; },
  inputSchema: wire.decodeWire(readFileSync(path.join(repo, 'integrations/dsh/wire-v1/WriterInputRefV1.schema.json'))),
  projectionSchema: wire.decodeWire(readFileSync(path.join(repo, 'integrations/dsh/wire-v1/WriterWireProjectionV1.schema.json'))),
  validateInput: async raw => Buffer.from(py('print(canonical_json_bytes(parse_model(sys.stdin.buffer.read(),c.WriterInputRefV1)).decode())', raw)),
  digestValue: async value => digest(value),
  evidenceFor: async () => { if (evidence === undefined) throw new wire.WireError('wire_evidence_not_ready'); return evidence; },
  sealProjection: async value => Buffer.from(py('print(canonical_json_bytes(c.seal_projection(strict_json_loads(sys.stdin.buffer.read()))).decode())', JSON.stringify(value))),
};
let ctx; let server; let handle; let parentHandle; let grants; let body; let sse; let rawCapture; let normalized; let observedBinding;
const loopRequests = [];
const adapterChunks = [];
let actualSends = 0;
let prepareSends = 0;
try {
  await renderer.verifyWriterComposition(composition);
  mkdirSync(path.join(output, 'node_modules/@code2paper'), { recursive: true });
  symlinkSync(path.join(runtime, 'node_modules/@deepseek-ai'), path.join(output, 'node_modules/@deepseek-ai'), 'dir');
  symlinkSync(staged, path.join(output, 'node_modules/@code2paper/dsh-bundle'), 'dir');
  mkdirSync(path.join(output, 'cfg'));
  mkdirSync(path.join(output, 'workspace'));
  const profileDir = path.join(devRoot, 'home/profiles/code2paper-dev-compat');
  const profile = loadProfileDirectory('stage03-joint', profileDir, path.join(runtime, 'node_modules/@deepseek-ai/dsh/package.json'));
  const cordis = path.join(output, 'cfg/cordis.yml'); writeFileSync(cordis, readFileSync(path.join(profileDir, 'cordis.yml')));
  const overlay = path.join(output, 'overlay.yml');
  writeFileSync(overlay, JSON.stringify([{ id: 'session-persistence-jsonl', config: { root: path.join(output, 'sessions'), compression: 'none' } }]));
  if (cfg.mode === 'observe') {
    const raw = readFileSync(cfg.terminal_raw_path, 'utf8');
    server = createServer((request, response) => {
      request.setEncoding('utf8'); let incoming = '';
      request.on('data', chunk => { incoming += chunk; });
      request.on('end', () => {
        actualSends += 1; if (actualSends > 1) { response.writeHead(500); response.end('extra request refused'); return; }
        body = incoming;
        const split = Math.floor(raw.length / 2);
        const events = [
          { choices: [{ index: 0, delta: { role: 'assistant', tool_calls: [{ index: 0, id: bootstrap.context.tool_call_id, type: 'function', function: { name: renderer.WRITER_TERMINAL, arguments: raw.slice(0, split) } }] }, finish_reason: null }] },
          { choices: [{ index: 0, delta: { tool_calls: [{ index: 0, function: { arguments: raw.slice(split) } }] }, finish_reason: null }] },
          { choices: [{ index: 0, delta: {}, finish_reason: 'tool_calls' }], usage: { prompt_tokens: 17, completion_tokens: 11 } },
        ];
        sse = `${events.map(event => `data: ${JSON.stringify(event)}\n\n`).join('')}data: [DONE]\n\n`;
        response.writeHead(200, { 'content-type': 'text/event-stream' }); response.end(sse);
      });
    });
    await new Promise(resolve => server.listen(cfg.fake_http_port ?? 0, '127.0.0.1', resolve));
    const address = server.address(); assert.ok(address !== null && typeof address !== 'string');
    cfg.observed_endpoint = `http://127.0.0.1:${address.port}`;
    const declaredEndpoint = bootstrap.composition.effective_config.fake_provider_endpoint;
    if (declaredEndpoint !== undefined) assert.equal(cfg.observed_endpoint, declaredEndpoint);
    process.env['C2P_STAGE03_TEST_ONLY_KEY'] = 'local-fake-service';
  }
  const patches = [...profile.layers.flatMap(layer => layer.patches), ...profile.patches,
    ...loadOverlayPatches('stage03-joint', path.join(repo, 'integrations/dsh/dev/offline.patch.yml')), ...loadOverlayPatches('stage03-joint', overlay)];
  ctx = await boot('stage03-joint', cordis, patches, host => {
    provideCmdline(host, { args: ['--host', '127.0.0.1', '--port', '0', '--no-open'], exit: () => {} });
    // Bound the controlled single-request fixture even when a terminal is rejected.
    host.on('agent/pre-step', (request, next) => request.step > 1 ? Promise.resolve({ kind: 'reject' }) : next());
    host.on('llm/stream', (request, next) => {
      loopRequests.push(request);
      return (async function* () { for await (const chunk of next()) { adapterChunks.push(chunk); yield chunk; } })();
    });
  });
  if (cfg.mode === 'observe') {
    assert.equal(input.effective_options.provider, 'deepseek');
    await ctx.plugin(PiAi, { providers: { deepseek: { apiKeyEnv: 'C2P_STAGE03_TEST_ONLY_KEY', baseURL: cfg.observed_endpoint,
      reasoning: 'off', retryPolicy: { mode: 'normal', maxRetries: 0 } } } });
    const capture = new terminal.TerminalArgumentCapture(); capture.install(ctx);
    // Controlled Host fixture only. This registry consumes the H02 seam; it is not R01 persistence.
    grants = new bindingApi.SessionBindings({ caller: { executionId: bootstrap.scope.execution_id, runId: 'stage03-controlled-run', hostGeneration: ctx.code2paperBridge.hostGeneration },
      recorder: { claim: async request => ({ claimId: 'stage03-controlled-context-only', taskId: request.task.taskId,
        epoch: request.task.epoch, fence: bootstrap.context.fence, compositionRef: composition.digest, grantedAt: Date.now() }) } });
    const task = { taskId: bootstrap.scope.task_id, epoch: bootstrap.scope.task_epoch };
    const parentGrant = await grants.claim({ task, purpose: 'root' });
    parentHandle = await ctx.agents.create({ sessionId: `${bootstrap.context.session_id}-parent`, meta: { cwd: path.join(output, 'workspace') },
      setup: async (parentCtx, parent) => {
        await ctx.code2paperBridge.mountPreset(parentCtx);
        grants.bind(parent.session.id, parentGrant);
      } });
    const grant = await grants.claim({ task, purpose: 'child', parentClaimId: parentGrant.claimId });
    assert.equal(bootstrap.context.child_id, bootstrap.context.session_id, 'controlled child identity must name the actual native child session');
    let parsed;
    handle = await parentHandle.agent.ctx.agents.create({ sessionId: bootstrap.context.session_id, parentAgent: parentHandle.agent,
      meta: childSessionMeta(parentHandle.agent, 1, false),
      agentOptions: { provider: input.effective_options.provider, model: input.model, maxTokens: input.post_clamp_max_output_tokens },
      setup: async (agentCtx, agent) => {
        applyChildComposition(agentCtx, parentHandle.agent, {});
        grants.bind(agent.session.id, grant, { parentSessionId: parentHandle.agent.session.id });
        renderer.installNativeWriter(agentCtx, input, value => { parsed = value; });
      } });
    observedBinding = await renderer.renderWriterInput(handle.agent, input);
    handle.agent.followup(createUserMessage({ content: [{ type: 'text', text: input.task_view_json }], source: { kind: 'user' } }));
    await handle.agent.whenIdle();
    assert.equal(actualSends, 1); assert.equal(loopRequests.length, 1); assert.ok(isAgentLoopRequest(loopRequests[0]));
    assert.ok(parsed !== undefined, 'terminal guard must accept the controlled legal fixture');
    const provider = wire.decodeWire(Buffer.from(body));
    assert.deepEqual(provider.messages, [{ role: 'system', content: observedBinding.system_text }, { role: 'user', content: observedBinding.user_text }]);
    assert.deepEqual(provider.tools, observedBinding.tools.map(tool => ({ type: 'function', function: { ...tool, strict: false } })));
    assert.equal(provider.model, input.model); assert.equal(provider.max_tokens, input.post_clamp_max_output_tokens);
    assert.equal(provider.temperature, input.effective_options.temperature);
    if (input.effective_options.reasoningEffort === 'off') {
      assert.deepEqual(provider.thinking, { type: 'disabled' }); assert.equal(provider.reasoning_effort, undefined);
    } else {
      assert.deepEqual(provider.thinking, { type: 'enabled' }); assert.equal(provider.reasoning_effort, input.effective_options.reasoningEffort);
    }
    rawCapture = capture.raw(bootstrap.context.tool_call_id, { sessionId: handle.agent.session.id });
    assert.equal(rawCapture.state, 'captured'); assert.equal(rawCapture.text, readFileSync(cfg.terminal_raw_path, 'utf8'));
    const session = handle.agent.session.snapshotEvents(0);
    const toolCall = session.find(event => event.type === 'tool/call' && event.data.callId === bootstrap.context.tool_call_id);
    assert.ok(toolCall !== undefined); normalized = toolCall.data.arguments;
    const finish = adapterChunks.find(chunk => chunk.type === 'finish');
    const usage = adapterChunks.find(chunk => chunk.type === 'usage');
    assert.ok(finish !== undefined); assert.ok(usage !== undefined);
    await ctx.sessionPersistence.flush();
    const loopRaw = JSON.stringify(loopRequests[0], (key, value) => key === 'signal' ? undefined : value);
    const providerRef = artifact(body); const loopRef = artifact(loopRaw);
    const comparison = { binding: observedBinding, loop_digest: loopRef.bytes_digest, provider_digest: providerRef.bytes_digest };
    const equivalence = { schema_version: 'WriterWireEquivalenceV1', input_digest: input.input_digest,
      renderer_digest: input.renderer_digest, composition_digest: input.composition_digest, projection_material_digest: digest(observedBinding),
      loop_request_ref: loopRef, provider_wire_ref: providerRef, comparison_ref: artifact(JSON.stringify(comparison)), transport_whitelist: ['request_id', 'tool_call_id'] };
    const measurement = { schema_version: 'WriterMeasurementV1', input_digest: input.input_digest, renderer_digest: input.renderer_digest,
      tokenizer_digest: bootstrap.composition.files.tokenizer.digest, meter_version: bootstrap.composition.effective_config.meter_version,
      measured_input_tokens: [...Buffer.from(body)].length, context_tokens: cfg.context_tokens ?? 131072,
      safety_margin_tokens: cfg.safety_margin_tokens ?? 512, thinking_tokens: cfg.thinking_tokens ?? 0,
      post_clamp_max_output_tokens: input.post_clamp_max_output_tokens, measured_wire_digest: providerRef.bytes_digest };
    assert.equal(measurement.meter_version, 'controlled-utf8-byte-id/1');
    evidence = { binding: observedBinding, measurement_ref: artifact(JSON.stringify(measurement)), wire_equivalence_ref: artifact(JSON.stringify(equivalence)) };
    for (const [name, bytes] of [['provider-request.raw.json', body], ['provider-response.raw.sse', sse],
      ['loop-request.raw.json', loopRaw], ['adapter-arguments.raw.json', rawCapture.text], ['normalized-arguments.json', normalized],
      ['adapter-chunks.json', JSON.stringify(adapterChunks)],
      ['host-session-events.json', JSON.stringify(session)], ['host-binding.json', JSON.stringify({ child: grants.requireCurrent(handle.agent), parent: grants.requireCurrent(parentHandle.agent), native_parent_session_id: parentHandle.agent.session.id })],
      ['measurement.json', JSON.stringify(measurement)], ['wire-equivalence.json', JSON.stringify(equivalence)],
      ['wire-comparison.json', JSON.stringify(comparison)], ['evidence.json', JSON.stringify(evidence)]]) writeFileSync(path.join(output, name), bytes, { flag: 'wx' });
    const envelope = { schema_version: 'OutputEnvelopeV1', ...bootstrap.scope,
      child_id: handle.agent.session.id, session_id: handle.agent.session.id, turn_id: String(toolCall.data.turn),
      step_id: String(toolCall.data.step), tool_call_id: toolCall.data.callId, request_id: bootstrap.context.request_id,
      source: 'adapter_tool_arguments_delta', arguments_complete: true,
      provider_http: { status: 'observed', ref: artifact(sse, 'application/octet-stream') },
      adapter_arguments: { status: 'observed', ref: artifact(rawCapture.text) },
      normalized_arguments: { status: 'observed', ref: artifact(normalized) }, stop_reason: finish.reason.kind, usage: usage.usage };
    writeFileSync(path.join(output, 'output-envelope.json'), JSON.stringify(envelope, null, 2), { flag: 'wx' });
  }
  const before = actualSends;
  const projection = await ctx.code2paperBridge.prepare_projection(inputBytes, composition, authority);
  prepareSends += actualSends - before;
  assert.equal(prepareSends, 0);
  if (loopRequests.length > 0) renderer.compareWriterRequest(projection, loopRequests[0]);
  writeFileSync(path.join(output, 'projection.json'), py('print(canonical_json_bytes(parse_model(sys.stdin.buffer.read(),c.WriterWireProjectionV1)).decode())', JSON.stringify(projection)), { flag: 'wx' });
  writeFileSync(path.join(output, 'projection-ref.json'), JSON.stringify(artifact(JSON.stringify(projection)), null, 2), { flag: 'wx' });
} finally {
  if (handle !== undefined) { await handle.dispose(); grants?.release(handle.agent.session.id); }
  if (parentHandle !== undefined) { await parentHandle.dispose(); grants?.release(parentHandle.agent.session.id); }
  await ctx?.sessionPersistence.flush(); await ctx?.fiber.dispose();
  if (server !== undefined) { server.closeAllConnections(); await new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve())); }
  delete process.env['C2P_STAGE03_TEST_ONLY_KEY'];
  writeFileSync(path.join(output, 'release.json'), JSON.stringify({ mode: cfg.mode, actual_sends: actualSends, prepare_sends: prepareSends,
    server_listening: server?.listening ?? false, bindings_remaining: grants?.size ?? 0, fake_endpoint: cfg.observed_endpoint,
    source_scope: 'controlled Stage03 fixture, no R01/R02 claim or budget authority' }, null, 2), { flag: 'wx' });
}
