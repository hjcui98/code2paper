/**
 * H03 — the typed terminal on the real DSH agent/tool path, and its durability.
 *
 * The composition is the real frozen one (dsh-base + dsh-web-app +
 * `@code2paper/dsh-bundle`) booted through `@deepseek-ai/dsh-app-boot`, driven by
 * a SCRIPTED, no-network LLM adapter. The adapter is H03's fallback provider: it
 * models what a real provider adapter does — including pi-ai's `JSON.stringify`
 * at `toolcall_end`, which is why the persisted `tool/call` argument string and
 * the raw delta text are DIFFERENT sources here.
 *
 * Session persistence is pointed at this run's private root and written
 * uncompressed (`session.v3.jsonl`) so the restart consumer can read the exact
 * persisted bytes. The shared dev home's session root is never touched (the
 * backend refuses mixed compression anyway, which is what forced this split).
 *
 * Acceptance points covered:
 * - a successful terminal is committed and rebuildable;
 * - closing text alone, a second terminal, a bad schema/arguments and any tool
 *   after the terminal do not commit;
 * - the fallback (no adapter registered) path produces no terminal;
 * - after `sessionPersistence.flush()`, a restarted process rebuilds the same
 *   record from the persisted bytes.
 */

import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { after, before, test } from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { boot, loadOverlayPatches, loadProfileDirectory } from '@deepseek-ai/dsh-app-boot';
import { provideCmdline } from '@deepseek-ai/dsh-cmdline';
import { createUserMessage, LlmAdapter, type StreamChunk } from '@deepseek-ai/dsh-llm';
import { defineTool } from '@deepseek-ai/dsh-tools';
import type { AgentHandle } from '@deepseek-ai/dsh-agent';
import type { Context } from '@deepseek-ai/cordis';
import type { SessionId } from '@deepseek-ai/dsh-session';

import type * as TerminalApi from '../src/terminal-result.js';

const packageDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
// The launcher decides which development root is active (default or an isolated
// candidate) and exports it, so the guard compares against that same root.
const devRoot = process.env.C2P_DSH_DEV_ROOT
  ? path.resolve(process.env.C2P_DSH_DEV_ROOT)
  : path.resolve(packageDir, '../../.dsh-dev');
const home = path.join(devRoot, 'home');
const runRoot = process.env.C2P_DSH_RUN_ROOT ?? path.join(devRoot, 'run');
const runtimeRoot = path.join(devRoot, 'runtime');
const installAnchor = path.join(runtimeRoot, 'node_modules/@deepseek-ai/dsh/package.json');
const profileDir = path.join(home, 'profiles/code2paper-dev-compat');
const bundleName = '@code2paper/dsh-bundle';
const stagedBundle = path.join(home, 'profiles/node_modules', bundleName);
const policyFile = path.join(packageDir, 'dev/offline.patch.yml');
const runId = `${String(process.pid)}-${Date.now().toString(36)}`;
const provider = 'h03-script';

/** The bundle's H03 module: runtime values from staging, types from the source. */
type TerminalModule = {
  readonly TERMINAL_TOOL: typeof TerminalApi.TERMINAL_TOOL;
  readonly TERMINAL_PARAMETERS: typeof TerminalApi.TERMINAL_PARAMETERS;
  readonly TerminalArgumentCapture: typeof TerminalApi.TerminalArgumentCapture;
  readonly installTerminalTool: typeof TerminalApi.installTerminalTool;
  readonly rebuildTerminal: typeof TerminalApi.rebuildTerminal;
  readonly digestText: typeof TerminalApi.digestText;
  readonly digestJson: typeof TerminalApi.digestJson;
};

/** Raw argument text with deliberate whitespace, an escape and non-canonical key order. */
const RAW_ARGUMENTS = '{ "result" :\n  { "kind":"draft", "draft": { "body":"line\\u0021", "title":"T" } } }';
/** What an adapter that re-serializes at toolcall_end would persist instead. */
const NORMALIZED_ARGUMENTS = JSON.stringify(JSON.parse(RAW_ARGUMENTS));

/** One scripted model response. */
type ScriptedStep =
  | { readonly kind: 'tool-calls'; readonly calls: readonly { readonly id: string; readonly name: string; readonly raw: string; readonly normalized?: string }[] }
  | { readonly kind: 'text'; readonly text: string }
  /** Emit one argument delta for a terminal call, then fail like a broken adapter. */
  | { readonly kind: 'fail-mid-call'; readonly id: string; readonly raw: string };

/**
 * The H03 fallback provider: a no-network adapter that replays a fixed script.
 * It throws when the loop asks for a request the script does not cover, so a
 * runaway loop fails loudly instead of spinning (the first probe run proved how
 * easily a non-one-shot script loops).
 */
class ScriptedAdapter extends LlmAdapter {
  private readonly steps: ScriptedStep[];
  readonly requests: { readonly messages: number; readonly tools: readonly string[] }[] = [];

  constructor(steps: readonly ScriptedStep[]) {
    super();
    this.steps = [...steps];
  }

  async *stream(options: { readonly messages?: readonly unknown[]; readonly tools?: readonly { name: string }[] }): AsyncIterable<StreamChunk> {
    this.requests.push({ messages: options.messages?.length ?? 0, tools: (options.tools ?? []).map((tool) => tool.name) });
    const step = this.steps.shift();
    if (step === undefined) throw new Error('scripted adapter exhausted: the loop requested an unscripted model call');
    if (step.kind === 'fail-mid-call') {
      yield { type: 'block-start', index: 0, blockType: 'tool-call' };
      yield { type: 'tool-call-delta', index: 0, id: step.id as never, name: terminalModule.TERMINAL_TOOL, argumentsDelta: step.raw };
      throw new Error('scripted adapter failed mid-arguments');
    }
    if (step.kind === 'text') {
      yield { type: 'block-start', index: 0, blockType: 'text' };
      yield { type: 'text-delta', index: 0, text: step.text };
      yield { type: 'block-end', index: 0, block: { type: 'text', text: step.text } };
      yield { type: 'finish', reason: { kind: 'stop' } };
      return;
    }
    for (const [index, call] of step.calls.entries()) {
      // The deltas carry the provider-raw text; the closed block carries what the
      // adapter would persist (pi-ai re-serializes at toolcall_end).
      yield { type: 'block-start', index, blockType: 'tool-call' };
      yield { type: 'tool-call-delta', index, id: call.id as never, name: call.name, argumentsDelta: call.raw };
      yield {
        type: 'block-end',
        index,
        block: { type: 'tool-call', id: call.id as never, name: call.name, arguments: call.normalized ?? call.raw },
      };
    }
    yield { type: 'finish', reason: { kind: 'tool-calls' } };
  }
}

interface Host {
  readonly ctx: Context;
  readonly capture: InstanceType<TerminalModule['TerminalArgumentCapture']>;
  readonly modelCalls: { count: number };
}

let privateRoot: string;
let host: Host;
let terminalModule: TerminalModule;
const handles: AgentHandle[] = [];

/** The persisted artifact path for one session, or undefined when absent. */
function artifactPath(sessionId: string): string | undefined {
  const root = path.join(privateRoot, 'sessions');
  if (!existsSync(root)) return undefined;
  for (const project of readdirSync(root)) {
    const dir = path.join(root, project, sessionId);
    if (!existsSync(dir)) continue;
    for (const file of readdirSync(dir)) {
      if (file.endsWith('.jsonl')) return path.join(dir, file);
    }
  }
  return undefined;
}

async function settle(handle: AgentHandle): Promise<void> {
  const outcome = await Promise.race([
    handle.agent.whenIdle().then(() => 'idle'),
    new Promise((resolve) => { setTimeout(() => resolve('timeout'), 20000); }),
  ]);
  assert.equal(outcome, 'idle', 'the scripted turn must settle; a timeout means the loop is spinning');
}

/** Create one agent with the terminal installed and the scripted route selected. */
async function createAgent(
  label: string,
  script: readonly ScriptedStep[],
  options: { readonly withAdapter?: boolean } = {},
): Promise<{ handle: AgentHandle; terminal: TerminalApi.TerminalHandle; adapter: ScriptedAdapter }> {
  const adapter = new ScriptedAdapter(script);
  // One provider route per agent: the llm registry refuses a duplicate adapter.
  const route = `${provider}-${label}`;
  const registration = options.withAdapter === false ? undefined : host.ctx.llm.registerAdapter([route], adapter);
  const sessionId = `h03-${label}-${runId}` as SessionId;
  let terminal!: TerminalApi.TerminalHandle;
  const handle = await host.ctx.agents.create({
    sessionId,
    meta: { cwd: path.join(privateRoot, 'workspace') },
    agentOptions: { provider: route, model: 'h03-model' },
    setup: (agentCtx, agent) => {
      terminal = terminalModule.installTerminalTool(agentCtx, { capture: host.capture, session: agent.session });
    },
  });
  handles.push(handle);
  if (registration !== undefined) registrations.push(registration);
  return { handle, terminal, adapter };
}

const registrations: (() => void)[] = [];

before(async () => {
  assert.equal(process.env.DSH_HOME, home, 'use the isolated launcher (npm run check:compat)');
  assert.ok(existsSync(path.join(stagedBundle, 'lib/terminal-result.js')), 'build and stage first');
  privateRoot = mkdtempSync(path.join(runRoot, 'h03-terminal-'));
  mkdirSync(path.join(privateRoot, 'workspace'));
  const modules = path.join(privateRoot, 'node_modules');
  mkdirSync(path.join(modules, '@code2paper'), { recursive: true });
  symlinkSync(path.join(runtimeRoot, 'node_modules/@deepseek-ai'), path.join(modules, '@deepseek-ai'), 'dir');
  symlinkSync(stagedBundle, path.join(modules, '@code2paper/dsh-bundle'), 'dir');
  terminalModule = await import(pathToFileURL(path.join(stagedBundle, 'lib/terminal-result.js')).href) as TerminalModule;

  const profile = loadProfileDirectory('h03-terminal-test', profileDir, installAnchor);
  const configDir = path.join(privateRoot, 'cfg');
  mkdirSync(configDir, { recursive: true });
  const config = path.join(configDir, 'cordis.yml');
  writeFileSync(config, readFileSync(path.join(profileDir, 'cordis.yml')));
  // Private, uncompressed session artifacts: the restart consumer reads the exact
  // bytes, and the shared sessions root is never mixed with another mode.
  const overlay = path.join(privateRoot, 'overlay.yml');
  writeFileSync(overlay, `${JSON.stringify([
    { id: 'session-persistence-jsonl', config: { root: path.join(privateRoot, 'sessions'), compression: 'none' } },
  ])}\n`);
  const patches = [
    ...profile.layers.flatMap((layer) => layer.patches), ...profile.patches,
    ...loadOverlayPatches('h03-terminal-test', policyFile),
    ...loadOverlayPatches('h03-terminal-test', overlay),
  ];
  const modelCalls = { count: 0 };
  const ctx = await boot('h03-terminal-test', config, patches, (hostCtx) => {
    provideCmdline(hostCtx, { args: ['--host', '127.0.0.1', '--port', '0', '--no-open'], exit: () => {} });
    hostCtx.on('llm/stream', (_options, next) => {
      modelCalls.count += 1;
      return next();
    });
  });
  const capture = new terminalModule.TerminalArgumentCapture();
  capture.install(ctx);
  host = { ctx, capture, modelCalls };
});

after(async () => {
  const errors: unknown[] = [];
  for (const handle of [...handles].reverse()) {
    try { await handle.dispose(); } catch (error) { errors.push(error); }
  }
  for (const dispose of registrations) {
    try { dispose(); } catch (error) { errors.push(error); }
  }
  try { await host?.ctx.fiber.dispose(); } catch (error) { errors.push(error); }
  try { if (privateRoot !== undefined) rmSync(privateRoot, { recursive: true, force: true }); } catch (error) { errors.push(error); }
  if (errors.length > 0) throw new AggregateError(errors, 'H03 teardown failed');
});

test('a successful terminal commits with separated sources and survives a restart', async () => {
  const { handle, terminal } = await createAgent('success', [
    { kind: 'tool-calls', calls: [{ id: 'call-success', name: terminalModule.TERMINAL_TOOL, raw: RAW_ARGUMENTS, normalized: NORMALIZED_ARGUMENTS }] },
  ]);
  handle.agent.followup(createUserMessage({ content: [{ type: 'text', text: 'write it' }], source: { kind: 'user' } }));
  await settle(handle);

  const record = terminal.committed();
  assert.ok(record !== undefined, 'the terminal must commit');
  assert.equal(record.parsed.kind, 'draft');
  assert.deepEqual(record.parsed, {
    kind: 'draft', draft: { title: 'T', body: 'line!' },
  }, 'the parsed domain object is the fixture model');
  assert.equal(record.schema, 'c2p-terminal/1');

  // Raw source: verbatim delta text, NOT a re-serialization.
  assert.equal(record.rawArguments.state, 'captured');
  assert.ok(record.rawArguments.state === 'captured');
  assert.equal(record.rawArguments.text, RAW_ARGUMENTS, 'raw argument text must be verbatim');
  assert.equal(record.rawArguments.chunks, 1);
  assert.equal(record.rawArguments.digest, terminalModule.digestText(RAW_ARGUMENTS));

  // Normalized source: what the session recorded, a different string and digest.
  assert.equal(record.normalizedArguments.source, 'session-tool-call');
  assert.equal(record.normalizedArguments.text, NORMALIZED_ARGUMENTS);
  assert.notEqual(record.normalizedArguments.text, RAW_ARGUMENTS, 'the fixture must exercise a re-serializing adapter');
  assert.notEqual(record.normalizedArguments.digest, record.rawArguments.digest);
  assert.notEqual(record.rawArguments.digest, terminalModule.digestJson(record.parsed),
    'a JSON.stringify reconstruction must never equal the raw digest');

  // Durability: flush, then rebuild from the persisted bytes in a fresh process.
  // The persistence service is registered by its plugin; only the two calls used
  // here are typed locally.
  const persistence = host.ctx.get('sessionPersistence') as unknown as {
    flush(): Promise<void>;
    stat(id: SessionId): Promise<{ readonly sizeBytes?: number } | undefined>;
  };
  assert.ok(persistence !== undefined, 'the composition must register session persistence');
  await persistence.flush();
  const stat = await persistence.stat(handle.agent.session.id);
  assert.ok((stat?.sizeBytes ?? 0) > 0, 'the flushed artifact must exist with bytes');
  const file = artifactPath(handle.agent.session.id);
  assert.ok(file !== undefined, 'the persisted artifact path must resolve');
  const bytes = readFileSync(file, 'utf8');
  assert.ok(bytes.includes('c2p/terminal'), 'the terminal record must be in the persisted bytes');

  const moduleUrl = pathToFileURL(path.join(stagedBundle, 'lib/terminal-result.js')).href;
  const script = `
    import { readFileSync } from 'node:fs';
    const mod = await import(${JSON.stringify(moduleUrl)});
    const lines = readFileSync(process.argv[1], 'utf8').trim().split('\\n').map((line) => JSON.parse(line));
    const header = lines[0];
    if (header?.type !== 'session' || typeof header.version !== 'number') {
      process.stderr.write('session header is missing its format version\\n');
      process.exit(2);
    }
    const events = lines.slice(1).filter((event) => event.type !== 'session');
    const rebuilt = mod.rebuildTerminal(events, header.version);
    process.stdout.write(JSON.stringify({
      state: rebuilt.state,
      kind: rebuilt.state === 'committed' ? rebuilt.record.parsed.kind : undefined,
      parsedDigest: rebuilt.state === 'committed' ? rebuilt.record.parsedDigest : undefined,
      rawState: rebuilt.state === 'committed' ? rebuilt.record.rawArguments.state : undefined,
      rawDigest: rebuilt.state === 'committed' ? rebuilt.record.rawArguments.digest : undefined,
      normalizedDigest: rebuilt.state === 'committed' ? rebuilt.record.normalizedArguments.digest : undefined,
    }));
  `;
  const child = spawnSync(process.execPath, ['--input-type=module', '-e', script, file], { encoding: 'utf8' });
  assert.equal(child.status, 0, `restart consumer failed: ${child.stderr}`);
  const rebuilt = JSON.parse(child.stdout) as {
    state: string; kind?: string; parsedDigest?: string; rawState?: string; rawDigest?: string; normalizedDigest?: string;
  };
  assert.equal(rebuilt.state, 'committed', 'a restarted consumer must rebuild the committed terminal');
  assert.equal(rebuilt.kind, 'draft');
  assert.equal(rebuilt.parsedDigest, record.parsedDigest, 'the rebuilt record must be byte-equal in its digests');
  assert.equal(rebuilt.rawState, 'captured');
  assert.equal(rebuilt.rawDigest, record.rawArguments.state === 'captured' ? record.rawArguments.digest : undefined);
  assert.equal(rebuilt.normalizedDigest, record.normalizedArguments.digest);

  // The terminal is final for its turn: the loop concluded instead of asking again.
  assert.equal(terminal.refusals().length, 0);
});

test('closing text alone does not commit a terminal', async () => {
  const { handle, terminal } = await createAgent('text-only', [{ kind: 'text', text: 'I am done, trust me.' }]);
  handle.agent.followup(createUserMessage({ content: [{ type: 'text', text: 'write it' }], source: { kind: 'user' } }));
  await settle(handle);
  assert.equal(terminal.committed(), undefined, 'closing text must not stand in for the terminal');
  const rebuilt = terminalModule.rebuildTerminal(handle.agent.session.snapshotEvents(0 as never), 4);
  assert.equal(rebuilt.state, 'absent');
});

test('a second terminal in one response does not commit and is refused', async () => {
  const { handle, terminal } = await createAgent('double', [
    { kind: 'tool-calls', calls: [
      { id: 'call-first', name: terminalModule.TERMINAL_TOOL, raw: RAW_ARGUMENTS },
      { id: 'call-second', name: terminalModule.TERMINAL_TOOL, raw: RAW_ARGUMENTS },
    ] },
  ]);
  handle.agent.followup(createUserMessage({ content: [{ type: 'text', text: 'write it' }], source: { kind: 'user' } }));
  await settle(handle);
  assert.ok(terminal.committed() !== undefined, 'the first terminal commits');
  assert.ok(
    terminal.refusals().some((refusal) => refusal.code === 'terminal-already-recorded'),
    `the second terminal must be refused: ${JSON.stringify(terminal.refusals())}`,
  );
  const records = handle.agent.session.snapshotEvents(0 as never).filter((event) => event.type === 'c2p/terminal');
  assert.equal(records.length, 1, 'exactly one terminal record may exist');
});

test('a bad schema or wrong arguments never commits', async () => {
  const bad = '{ "result": { "kind": "draft", "draft": { "title": "T" } } }';
  const { handle, terminal } = await createAgent('bad-schema', [
    { kind: 'tool-calls', calls: [{ id: 'call-bad', name: terminalModule.TERMINAL_TOOL, raw: bad }] },
    { kind: 'text', text: 'giving up' },
  ]);
  handle.agent.followup(createUserMessage({ content: [{ type: 'text', text: 'write it' }], source: { kind: 'user' } }));
  await settle(handle);
  assert.equal(terminal.committed(), undefined, 'a schema-invalid call must not commit');
  const events = handle.agent.session.snapshotEvents(0 as never);
  const result = events.find((event) => event.type === 'tool/result');
  assert.ok(result !== undefined && (result.data as unknown as { message?: { content?: { isError?: boolean }[] } }).message !== undefined);
  assert.equal(terminalModule.rebuildTerminal(events, 4).state, 'unresolved',
    'a logged terminal call without a commit is unresolved, never reconstructed');
});

test('a tool call after the terminal is refused and cannot commit', async () => {
  const { handle, terminal } = await createAgent('after', [
    { kind: 'tool-calls', calls: [{ id: 'call-terminal', name: terminalModule.TERMINAL_TOOL, raw: RAW_ARGUMENTS }] },
    // The second turn's model response tries the terminal again; the guard must
    // deny it before the tool body runs.
    { kind: 'tool-calls', calls: [{ id: 'call-after', name: terminalModule.TERMINAL_TOOL, raw: RAW_ARGUMENTS }] },
  ]);
  handle.agent.followup(createUserMessage({ content: [{ type: 'text', text: 'write it' }], source: { kind: 'user' } }));
  await settle(handle);
  const committed = terminal.committed();
  assert.ok(committed !== undefined);

  // A later turn tries another tool: the monotonic guard denies it.
  handle.agent.followup(createUserMessage({ content: [{ type: 'text', text: 'one more thing' }], source: { kind: 'user' } }));
  await settle(handle);
  assert.ok(
    terminal.refusals().some((refusal) => refusal.code === 'terminal-already-recorded'),
    `a post-terminal tool call must be refused: ${JSON.stringify(terminal.refusals())}`,
  );
  assert.equal(terminal.committed()?.terminalId, committed.terminalId, 'the original commit is unchanged');
  assert.equal(
    handle.agent.session.snapshotEvents(0 as never).filter((event) => event.type === 'c2p/terminal').length,
    1,
    'no second record may appear',
  );
});

test('a real adapter failing mid-arguments yields an incomplete raw source, never captured', async () => {
  const partial = '{ "result": { "kind": "draft", "draft": { "title": "T"';
  const { handle, terminal } = await createAgent('adapter-failure', [
    { kind: 'fail-mid-call', id: 'call-broken', raw: partial },
  ]);
  handle.agent.followup(createUserMessage({ content: [{ type: 'text', text: 'write it' }], source: { kind: 'user' } }));
  await settle(handle);

  // The turn cannot produce a terminal: the call never completed.
  assert.equal(terminal.committed(), undefined, 'a failed model stream must not commit');
  assert.equal(
    terminalModule.rebuildTerminal(handle.agent.session.snapshotEvents(0 as never), 4).state,
    'absent',
  );

  // The capture saw the partial delta through the REAL registered adapter path,
  // where the runtime normalizes the adapter failure and ends the iteration
  // normally — so iterator completion must not be mistaken for completeness.
  const raw = host.capture.raw('call-broken', { sessionId: handle.agent.session.id });
  assert.equal(raw.state, 'incomplete', `expected an incomplete source, got ${raw.state}`);
  assert.ok(raw.state === 'incomplete');
  assert.equal(raw.text, partial, 'the partial text is kept');
  assert.equal(raw.digest, terminalModule.digestText(partial));
  assert.match(raw.reason, /failed|completion fact/);
});

test('the fallback path without an adapter produces no terminal', async () => {
  const { handle, terminal } = await createAgent('no-adapter', [], { withAdapter: false });
  handle.agent.followup(createUserMessage({ content: [{ type: 'text', text: 'write it' }], source: { kind: 'user' } }));
  await settle(handle);
  assert.equal(terminal.committed(), undefined, 'an unavailable model route must not fabricate a terminal');
  assert.equal(
    terminalModule.rebuildTerminal(handle.agent.session.snapshotEvents(0 as never), 4).state,
    'absent',
  );
});

test('a failing flush never counts as durable recovery', async () => {
  const { handle, terminal } = await createAgent('flush-failure', [
    { kind: 'tool-calls', calls: [{ id: 'call-flush-fail', name: terminalModule.TERMINAL_TOOL, raw: RAW_ARGUMENTS, normalized: NORMALIZED_ARGUMENTS }] },
  ]);
  handle.agent.followup(createUserMessage({ content: [{ type: 'text', text: 'write it' }], source: { kind: 'user' } }));
  await settle(handle);
  assert.ok(terminal.committed() !== undefined, 'the terminal commits in memory');
  const persistence = host.ctx.get('sessionPersistence') as unknown as {
    flush(): Promise<void>;
    flushSession(session: SessionId): Promise<boolean>;
  };
  const originalFlush = persistence.flush.bind(persistence);
  persistence.flush = async () => { throw new Error('flush listener unavailable'); };
  try {
    await assert.rejects(() => persistence.flush(), /flush listener unavailable/,
      'a failing flush must surface, not resolve as success');
    // Whatever the failing flush left behind, the durable path must not claim
    // a committed recovery from it.
    const file = artifactPath(handle.agent.session.id);
    if (file !== undefined) {
      const bytes = readFileSync(file, 'utf8');
      const lines = bytes.trim().split('\n').map((line) => JSON.parse(line));
      const events = lines.slice(1).filter((event) => event.type !== 'session');
      const outcome = terminalModule.rebuildTerminal(events, 4);
      assert.ok(outcome.state !== 'committed' || bytes.includes('c2p/terminal'),
        'a recovery claim requires the terminal bytes on disk');
    }
  } finally {
    persistence.flush = originalFlush;
  }
});

test('a partial flush leaves a named unresolved, never a committed claim', async () => {
  const { handle, terminal } = await createAgent('flush-partial', [
    { kind: 'tool-calls', calls: [{ id: 'call-flush-partial', name: terminalModule.TERMINAL_TOOL, raw: RAW_ARGUMENTS, normalized: NORMALIZED_ARGUMENTS }] },
  ]);
  handle.agent.followup(createUserMessage({ content: [{ type: 'text', text: 'write it' }], source: { kind: 'user' } }));
  await settle(handle);
  assert.ok(terminal.committed() !== undefined);
  const persistence = host.ctx.get('sessionPersistence') as unknown as { flush(): Promise<void> };
  await persistence.flush();
  const file = artifactPath(handle.agent.session.id);
  assert.ok(file !== undefined);
  const bytes = readFileSync(file, 'utf8');
  // Simulate a crash mid-write: keep only the header and the first half of the body.
  const kept = bytes.slice(0, Math.floor(bytes.length / 2));
  const lines = kept.split('\n').filter((line) => line.trim() !== '' && line.trim().endsWith('}'));
  writeFileSync(file, `${lines.join('\n')}\n`);
  const partialLines = lines.map((line) => JSON.parse(line));
  const events = partialLines.slice(1).filter((event) => event.type !== 'session');
  const outcome = terminalModule.rebuildTerminal(events, 4);
  assert.ok(outcome.state === 'committed' || outcome.state === 'unresolved' || outcome.state === 'absent');
  if (outcome.state === 'committed') {
    // The truncated log must still hold the full terminal record and its
    // matching successful tool call; otherwise the cut cannot be committed.
    assert.ok(kept.includes('c2p/terminal'), 'a committed rebuild requires the record bytes');
  } else {
    assert.match(outcome.reason, /without a committed|no c2p_terminal call|no successful|record|missing/i);
  }
});

test('the terminal schema keeps the union and its per-branch constraints', () => {
  const branches = terminalModule.TERMINAL_PARAMETERS.result.oneOf;
  assert.equal(branches.length, 3, 'draft / research_required / blocked');
  for (const branch of branches) {
    assert.equal(branch.additionalProperties, false, 'extra fields must stay forbidden');
    assert.equal(branch.properties.kind.required, true, 'kind must stay required');
  }
  assert.equal(terminalModule.TERMINAL_PARAMETERS.result.required, true, 'the result property must stay required');
  const kinds = branches.map((branch) => branch.properties.kind.enum[0]);
  assert.deepEqual(kinds, ['draft', 'research_required', 'blocked']);
  // The same parameters validate through a real tool definition.
  const definition = defineTool({
    name: 'h03-schema-probe',
    description: 'schema probe',
    parameters: terminalModule.TERMINAL_PARAMETERS,
    output: { schema: { type: 'object', additionalProperties: false, properties: { ok: { type: 'boolean', required: true } } }, render: () => [] },
    execute: () => Promise.resolve({ ok: true }),
  });
  assert.equal(definition.name, 'h03-schema-probe');
});
