/**
 * Same bound child: accounting → adapter → terminal → settle → flush →
 * a new process rebuild. A bare request must not pollute the legal source,
 * and a synthetic recovery result is not a successful terminal.
 */
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { after, before, test } from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { boot, loadOverlayPatches, loadProfileDirectory } from '@deepseek-ai/dsh-app-boot';
import { provideCmdline } from '@deepseek-ai/dsh-cmdline';
import { LlmAdapter } from '@deepseek-ai/dsh-llm';
import type { GenerateOptions, StreamChunk } from '@deepseek-ai/dsh-llm';
import type { Context } from '@deepseek-ai/cordis';
import type { SessionId } from '@deepseek-ai/dsh-session';

import type * as AccountingApi from '../src/request-accounting.js';
import type * as ContractApi from '../src/request-contract.js';
import type * as TerminalApi from '../src/terminal-result.js';

const packageDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const devRoot = process.env.C2P_DSH_DEV_ROOT
  ? path.resolve(process.env.C2P_DSH_DEV_ROOT)
  : path.resolve(packageDir, '../../.dsh-dev');
const home = path.join(devRoot, 'home');
const runRoot = process.env.C2P_DSH_RUN_ROOT ?? path.join(devRoot, 'run');
const runtimeRoot = path.join(devRoot, 'runtime');
const installAnchor = path.join(runtimeRoot, 'node_modules/@deepseek-ai/dsh/package.json');
const profileDir = path.join(home, 'profiles/code2paper-dev-compat');
const policyFile = path.join(packageDir, 'dev/offline.patch.yml');
const stagedBundle = path.join(home, 'profiles/node_modules/@code2paper/dsh-bundle');
const runId = `${String(process.pid)}-${Date.now().toString(36)}`;
const ROUTE = 'c2p-joint-mock';
const MODEL = 'joint-model';
const ARGUMENTS = '{"result":{"kind":"draft","draft":{"title":"Joint","body":"ok"}}}';
let prepareHold: Promise<void> | undefined;
let prepareOpened: (() => void) | undefined;


class JointAdapter extends LlmAdapter {
  readonly calls: string[] = [];
  private phase: 'tool' | 'stop' | 'done' = 'tool';

  override providerInfo(provider: string): { id: string; name: string } {
    return { id: provider, name: 'joint mock' };
  }
  override async listModels(): Promise<never[]> { return []; }
  override async resolveModel(provider: string, model: string) {
    return { provider, id: model, name: model, context: { contextWindow: 8192 }, defaultMaxTokens: 1024 };
  }
  override async prepareCall(provider: string, model: string) {
    if (prepareHold !== undefined) {
      prepareOpened?.();
      await prepareHold;
    }
    return { model: await this.resolveModel(provider, model), stream: (options: GenerateOptions) => this.stream(options) };
  }
  override async *stream(options: GenerateOptions): AsyncIterable<StreamChunk> {
    this.calls.push(String(options.sessionId));
    if (this.phase === 'tool') {
      this.phase = 'stop';
      yield { type: 'block-start', index: 0, blockType: 'tool-call' };
      yield { type: 'tool-call-delta', index: 0, id: 'joint-call' as never, name: 'c2p_terminal', argumentsDelta: ARGUMENTS };
      yield { type: 'block-end', index: 0, block: { type: 'tool-call', id: 'joint-call' as never, name: 'c2p_terminal', arguments: ARGUMENTS } };
      yield { type: 'usage', usage: { inputTokens: 11, outputTokens: 7 } };
      yield { type: 'finish', reason: { kind: 'tool-calls' } };
      return;
    }
    if (this.phase === 'stop') {
      this.phase = 'done';
      yield { type: 'block-start', index: 0, blockType: 'text' };
      yield { type: 'text-delta', index: 0, text: 'done' };
      yield { type: 'block-end', index: 0, block: { type: 'text', text: 'done' } };
      yield { type: 'usage', usage: { inputTokens: 12, outputTokens: 2 } };
      yield { type: 'finish', reason: { kind: 'stop' } };
      return;
    }
    throw new Error('joint adapter exhausted');
  }
}

class Recorder implements ContractApi.RequestRecorder {
  readonly events: string[] = [];
  private minted = 0;
  async reserve(request: ContractApi.RequestReserveRequest): Promise<ContractApi.ReservationReceipt> {
    this.minted += 1;
    this.events.push(`reserve:${String(request.binding.sessionId)}`);
    return {
      contractVersion: 'c2p-host-request/1',
      reservationId: `res-${String(this.minted)}`, requestId: `req-${String(this.minted)}`,
      binding: request.binding, digest: request.digest, grantedAt: Date.now(),
    };
  }
  async dispatch(request: ContractApi.RequestDispatchRequest): Promise<ContractApi.DispatchReceipt> {
    this.events.push(`dispatch:${String(request.reservation.binding.sessionId)}`);
    return {
      contractVersion: 'c2p-host-request/1',
      requestId: request.reservation.requestId, reservationId: request.reservation.reservationId,
      digest: request.digest, stage: 'dispatch-recorded', recordedAt: Date.now(),
    };
  }
  async settle(request: ContractApi.RequestSettleRequest): Promise<ContractApi.SettlementReceipt> {
    this.events.push(`settle:${request.finish.kind}`);
    return {
      contractVersion: 'c2p-host-request/1', requestId: request.requestId, settlementId: 'set',
      finish: request.finish, response: request.response, settledAt: Date.now(),
    };
  }
  async markUnknown(request: ContractApi.RequestMarkUnknownRequest): Promise<ContractApi.UnknownReceipt> {
    this.events.push(`unknown:${request.reason}`);
    return {
      contractVersion: 'c2p-host-request/1', requestId: request.requestId,
      lastStage: request.lastStage, reason: request.reason, uncertainty: 'send-outcome-unknown', recordedAt: Date.now(),
    };
  }
}

let privateRoot: string;
let ctx: Context;
let childAgent: { session: { id: SessionId }; whenIdle(): Promise<void>; cancel(reason: { kind: string }): void };
let childRun: { result: Promise<unknown>; dispose(): Promise<void> };
let terminal: TerminalApi.TerminalHandle;
let adapter: JointAdapter;
let recorder: Recorder;
let terminalModule: {
  rebuildTerminal: typeof TerminalApi.rebuildTerminal;
  installTerminalTool: typeof TerminalApi.installTerminalTool;
  TerminalArgumentCapture: typeof TerminalApi.TerminalArgumentCapture;
};

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

const jointDiagnostics: { kind: string; detail: string }[] = [];

before(async () => {
  assert.equal(process.env.DSH_HOME, home, 'use the isolated launcher');
  assert.ok(
    // The audited native-params variant retains the same private-origin
    // contract and must pass every original acceptance assertion below.
    ['0.2.0-rc.1+loop-origin.1', '0.2.0-rc.1+loop-origin.1-built',
      '0.2.0-rc.1+loop-origin.1+tool-choice.2'].includes(String(process.env.C2P_DSH_CANDIDATE)),
    `the launcher must pass this delivery's candidate: ${String(process.env.C2P_DSH_CANDIDATE)}`);
  privateRoot = mkdtempSync(path.join(runRoot, 'joint-child-'));
  mkdirSync(path.join(privateRoot, 'workspace'));
  const modules = path.join(privateRoot, 'node_modules');
  mkdirSync(path.join(modules, '@code2paper'), { recursive: true });
  symlinkSync(path.join(runtimeRoot, 'node_modules/@deepseek-ai'), path.join(modules, '@deepseek-ai'), 'dir');
  symlinkSync(stagedBundle, path.join(modules, '@code2paper/dsh-bundle'), 'dir');
  const accounting = await import(pathToFileURL(path.join(stagedBundle, 'lib/request-accounting.js')).href) as typeof AccountingApi;
  const sessionApi = await import(pathToFileURL(path.join(stagedBundle, 'lib/session-binding.js')).href) as typeof import('../src/session-binding.js');
  const dispatchApi = await import(pathToFileURL(path.join(stagedBundle, 'lib/role-dispatch.js')).href) as typeof import('../src/role-dispatch.js');
  terminalModule = await import(pathToFileURL(path.join(stagedBundle, 'lib/terminal-result.js')).href) as typeof terminalModule;
  const capture = new terminalModule.TerminalArgumentCapture();
  recorder = new Recorder();
  adapter = new JointAdapter();

  const profile = loadProfileDirectory('joint-child', profileDir, installAnchor);
  const configDir = path.join(privateRoot, 'cfg');
  mkdirSync(configDir, { recursive: true });
  const config = path.join(configDir, 'cordis.yml');
  writeFileSync(config, readFileSync(path.join(profileDir, 'cordis.yml')));
  const overlay = path.join(privateRoot, 'overlay.yml');
  writeFileSync(overlay, `${JSON.stringify([
    { id: 'session-persistence-jsonl', config: { root: path.join(privateRoot, 'sessions'), compression: 'none' } },
  ])}\n`);
  const patches = [
    ...profile.layers.flatMap((layer) => layer.patches), ...profile.patches,
    ...loadOverlayPatches('joint-child', policyFile),
    ...loadOverlayPatches('joint-child', overlay),
  ];
  ctx = await boot('joint-child', config, patches, (hostCtx) => {
    provideCmdline(hostCtx, { args: ['--host', '127.0.0.1', '--port', '0', '--no-open'], exit: () => {} });
  });
  capture.install(ctx);
  const authorizations = new accounting.DispatchAuthorizations();
  const bridge = ctx.get('code2paperBridge') as unknown as { hostGeneration: number };
  const bindings = new sessionApi.SessionBindings({
    caller: { executionId: 'joint-execution', runId: 'joint-run', hostGeneration: bridge.hostGeneration },
    recorder: {
      async claim(request: { task: { taskId: string; epoch: number }; purpose: string }) {
        return {
          claimId: 'joint-claim', taskId: request.task.taskId, epoch: request.task.epoch,
          fence: 1, compositionRef: 'joint', grantedAt: Date.now(),
        };
      },
    },
  });
  accounting.installRequestAccounting(ctx, {
    bindings,
    recorder,
    route: ROUTE,
    purpose: 'writer',
    outputCap: { version: 'h04-test-cap/1', cap: () => 256 },
    authorizations,
    isProtectedAgent: () => true,
    diagnostics: (event) => { jointDiagnostics.push({ kind: event.kind, detail: event.detail }); },
  });
  ctx.llm.registerAdapter([ROUTE], accounting.gatedAdapter(adapter, authorizations) as never);
  dispatchApi.registerCode2PaperSpawn(ctx, { bindings });
  ctx.on('agent/created', ({ agent }: { agent: { ctx: Context; session: { id: SessionId } } }) => {
    terminal = terminalModule.installTerminalTool(agent.ctx as never, { capture, session: agent.session as never });
    return undefined;
  });
  const root = await sessionApi.createBoundRootAgent(ctx, {
    bindings,
    sessionId: `joint-root-${runId}` as SessionId,
    task: { taskId: 'task-joint', epoch: 1 },
    cwd: path.join(privateRoot, 'workspace'),
  });
  const dispatched = await dispatchApi.dispatchRole(ctx, {
    parent: root.handle.agent,
    role: 'writer',
    prompt: [{ type: 'text', text: 'write the terminal' }],
    signal: new AbortController().signal,
    bindings,
    agentOptions: { provider: ROUTE, model: MODEL, maxTokens: 64 },
  });
  childAgent = dispatched.run.localAgent as typeof childAgent;
  childRun = dispatched.run;
  assert.ok(terminal !== undefined, 'the child creation must install the terminal before its turn');

  // Wait-window source attack: hold the child inside the real prepareCall, then
  // try to take the preparation with the public agent, signal and session.
  let observed: { agent: { id: string }; signal: AbortSignal } | undefined;
  const stopObserve = ctx.on('agent/request', ((payload: { agent: { id: string }; signal: AbortSignal }, next: () => Promise<unknown>) => {
    if (observed === undefined) observed = payload;
    return next();
  }) as never);
  const opened = new Promise<void>((resolve) => { prepareOpened = resolve; });
  let releaseHold!: () => void;
  prepareHold = new Promise<void>((resolve) => { releaseHold = resolve; });
  await Promise.race([
    opened,
    new Promise((_resolve, reject) => { setTimeout(() => reject(new Error(`the child never entered preparation: diag=${JSON.stringify(jointDiagnostics)} events=${JSON.stringify(recorder.events)}`)), 10000); }),
  ]);
  assert.ok(observed !== undefined, 'the child preparation must be observable');
  const seen = observed;
  const agents = ctx.agents as unknown as {
    withInitiator<T>(agent: { id: string }, operation: () => T): Promise<T>;
  };
  const stolenChunks: StreamChunk[] = [];
  await agents.withInitiator(seen.agent, async () => {
    for await (const chunk of ctx.llm.stream({
      provider: ROUTE,
      model: MODEL,
      maxTokens: 64,
      messages: [{ role: 'user', content: [{ type: 'text', text: 'joint-wait-steal' }] }],
      sessionId: seen.agent.id as SessionId,
      signal: seen.signal,
    })) stolenChunks.push(chunk);
  });
  assert.ok(stolenChunks.some((chunk) => chunk.type === 'finish' && typeof chunk.reason !== 'string' && chunk.reason.kind === 'error'),
    `a prepare-wait steal must be refused: ${JSON.stringify(stolenChunks)}`);
  assert.equal(recorder.events.length, 0, `a refused steal must not reserve: ${JSON.stringify(recorder.events)}`);
  assert.equal(adapter.calls.length, 0, 'a refused steal must not reach the adapter');
  stopObserve();
  releaseHold();
  prepareHold = undefined;
});

after(async () => {
  const errors: unknown[] = [];
  try { await childRun?.dispose(); } catch (error) { errors.push(error); }
  try { await ctx?.fiber.dispose(); } catch (error) { errors.push(error); }
  try { if (privateRoot !== undefined) rmSync(privateRoot, { recursive: true, force: true }); } catch (error) { errors.push(error); }
  if (errors.length > 0) throw new AggregateError(errors, 'joint teardown failed');
});

test('one bound child accounts, commits, flushes, and rebuilds; a bare request does not pollute it', async () => {
  // The wait-window source attack (hold the child inside the real prepareCall,
  // then re-enter with the public agent, signal and session) runs in the
  // before() hook, where the child's single prepareCall is actually held. The
  // terminal tool concludes this child's turn, so no second prepareCall window
  // exists after it; the attack facts are already asserted there.

  const idle = await Promise.race([
    childAgent.whenIdle().then(() => 'idle'),
    new Promise((resolve) => { setTimeout(() => resolve('timeout'), 20000); }),
  ]);
  assert.equal(idle, 'idle', `joint turn did not settle; events=${JSON.stringify(recorder.events)}`);
  const record = terminal.committed();
  assert.ok(record !== undefined, `the terminal must commit; events=${JSON.stringify(recorder.events)} calls=${JSON.stringify(adapter.calls)}`);
  assert.equal(record.parsed.kind, 'draft');
  assert.ok(recorder.events.some((event) => event.startsWith('reserve:')));
  assert.ok(recorder.events.some((event) => event.startsWith('dispatch:')));
  assert.ok(recorder.events.includes('settle:unfinished') || recorder.events.includes('settle:settled'),
    `the tool request must be settled without inventing a stop: ${JSON.stringify(recorder.events)}`);
  assert.ok(!recorder.events.some((event) => event.startsWith('unknown:usage-missing')));
  assert.ok(adapter.calls.length >= 1);

  const rawBefore = JSON.stringify(record.rawArguments);
  const bare: GenerateOptions = {
    provider: ROUTE, model: MODEL, maxTokens: 64,
    messages: [{ role: 'user', content: [{ type: 'text', text: 'pollute' }] }],
    sessionId: childAgent.session.id,
  };
  const chunks: StreamChunk[] = [];
  for await (const chunk of ctx.llm.stream(bare)) chunks.push(chunk);
  assert.ok(chunks.some((chunk) => chunk.type === 'finish' && typeof chunk.reason !== 'string' && chunk.reason.kind === 'error'));
  assert.equal(JSON.stringify(terminal.committed()?.rawArguments), rawBefore, 'a bare request must not replace the legal source');
  assert.equal(terminal.committed()?.terminalId, record.terminalId);

  const persistence = ctx.get('sessionPersistence') as unknown as { flush(): Promise<void> };
  await persistence.flush();
  const file = artifactPath(String(childAgent.session.id));
  assert.ok(file !== undefined, 'flush must leave a jsonl artifact');
  const moduleUrl = pathToFileURL(path.join(stagedBundle, 'lib/terminal-result.js')).href;
  const script = `
    import { readFileSync } from 'node:fs';
    const mod = await import(${JSON.stringify(moduleUrl)});
    const lines = readFileSync(process.argv[1], 'utf8').trim().split('\\n').map((line) => JSON.parse(line));
    const header = lines[0];
    const events = lines.slice(1).filter((event) => event.type !== 'session');
    const rebuilt = mod.rebuildTerminal(events, header.version);
    const synthetic = mod.rebuildTerminal([
      ...events,
      { type: 'tool/result', seq: 999, data: {
        turn: rebuilt.state === 'committed' ? rebuilt.record.turn : 0,
        step: rebuilt.state === 'committed' ? rebuilt.record.step : 0,
        message: { role: 'tool', toolCallId: rebuilt.state === 'committed' ? rebuilt.record.callId : 'x', isError: true, content: [] },
        error: { name: 'ToolRecovery', code: 'TOOL_OUTCOME_UNKNOWN' },
      } },
    ], header.version);
    process.stdout.write(JSON.stringify({
      state: rebuilt.state,
      kind: rebuilt.state === 'committed' ? rebuilt.record.parsed.kind : undefined,
      synthetic: synthetic.state,
    }));
  `;
  const child = spawnSync(process.execPath, ['--input-type=module', '-e', script, file], { encoding: 'utf8' });
  assert.equal(child.status, 0, child.stderr);
  const rebuilt = JSON.parse(child.stdout) as { state: string; kind?: string; synthetic: string };
  assert.equal(rebuilt.state, 'committed');
  assert.equal(rebuilt.kind, 'draft');
  assert.equal(rebuilt.synthetic, 'unresolved', 'a synthetic unknown outcome must not count as the committed success');
});
