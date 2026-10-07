/**
 * H04 — cancellation, bounded cleanup and terminal recording at the seam.
 *
 * Origin contract (loop-origin.1): the patched runtime establishes a private
 * dispatch origin at the agent loop's own stream call site and consumes it
 * once at the real admission point. The middleware verifies that origin as
 * the sole source credential. Legal prepared/fallback dispatches are metered
 * exactly once; every publicly initiated dispatch (bare requests, copied
 * signals, nested re-entry, delayed replay, stolen handles) is refused with
 * zero reserve and zero adapter.
 *
 * `AgentHandle.dispose()` resolving is deliberately NOT used as a quiescence
 * proof anywhere here.
 */

import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { after, before, test } from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { boot, loadOverlayPatches, loadProfileDirectory } from '@deepseek-ai/dsh-app-boot';
import { provideCmdline } from '@deepseek-ai/dsh-cmdline';
import { LlmAdapter, LlmError } from '@deepseek-ai/dsh-llm';
import type { GenerateOptions, StreamChunk } from '@deepseek-ai/dsh-llm';
import type { Context } from '@deepseek-ai/cordis';
import type { AgentHandle } from '@deepseek-ai/dsh-agent';
import type { SessionId } from '@deepseek-ai/dsh-session';

import type * as AccountingApi from '../src/request-accounting.js';
import type * as ContractApi from '../src/request-contract.js';

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
const MOCK_PROVIDER = 'c2p-h04-cancel-mock';
const MOCK_MODEL = 'h04-cancel-model';

/** Resource inventory this experiment actually owns. */
const resources = {
  adapterStreams: 0,
  managedSubprocesses: 0,
  note: 'no managed subprocess is started by this experiment',
};

const adapterDispatches: { sessionId: string | undefined; label: string }[] = [];
let adapterLabel = 'unlabeled';
let adapterMode: 'normal' | 'omit-usage' | 'hang-return' | 'throw-return' | 'fail-next' | 'no-adapter-once' | 'no-adapter-always' = 'normal';
let prepareHold: Promise<void> | undefined;
let prepareEntered: (() => void) | undefined;

class CountingAdapter extends LlmAdapter {
  readonly adapterInstanceId: string;
  constructor(adapterInstanceId: string = 'default') {
    super();
    this.adapterInstanceId = adapterInstanceId;
  }
  private prepareCalls = 0;
  private noAdapterOnceTriggered = false;
  override providerInfo(provider: string): { id: string; name: string } {
    return { id: provider, name: `h04 cancel mock (${provider})` };
  }
  override async listModels(): Promise<never[]> { return []; }
  override async resolveModel(provider: string, model: string) {
    return { provider, id: model, name: `H04 cancel ${model}`, context: { contextWindow: 131072 }, defaultMaxTokens: 4096 };
  }
  override async prepareCall(provider: string, model: string) {
    if (adapterMode === 'no-adapter-once') {
      this.prepareCalls += 1;
      if (!this.noAdapterOnceTriggered) {
        this.noAdapterOnceTriggered = true;
        throw new LlmError('no adapter configured', 'NO_ADAPTER');
      }
    } else {
      this.noAdapterOnceTriggered = false;
    }
    if (adapterMode === 'no-adapter-always') {
      throw new LlmError('no adapter configured', 'NO_ADAPTER');
    }
    if (prepareHold !== undefined) {
      prepareEntered?.();
      await prepareHold;
    }
    return { model: await this.resolveModel(provider, model), stream: (options: GenerateOptions) => this.stream(options) };
  }
  override stream(options: GenerateOptions): AsyncIterable<StreamChunk> {
    resources.adapterStreams += 1;
    const effectiveLabel = this.adapterInstanceId === 'default' ? adapterLabel : `${this.adapterInstanceId}:${adapterLabel}`;
    adapterDispatches.push({ sessionId: options.sessionId === undefined ? undefined : String(options.sessionId), label: effectiveLabel });
    const mode = adapterMode;
    if (mode === 'fail-next') {
      const chunks: StreamChunk[] = [
        { type: 'block-start', index: 0, blockType: 'text' },
        { type: 'text-delta', index: 0, text: 'ok' },
      ];
      let index = 0;
      const iterator = {
        async next(): Promise<IteratorResult<StreamChunk>> {
          if (index >= chunks.length) throw new Error('iteration exploded');
          return { done: false, value: chunks[index++] as StreamChunk };
        },
        async return(): Promise<IteratorResult<StreamChunk>> {
          return { done: true, value: undefined };
        },
      };
      return { [Symbol.asyncIterator]: () => iterator };
    }
    if (mode === 'throw-return') {
      const chunks: StreamChunk[] = [
        { type: 'block-start', index: 0, blockType: 'text' },
        { type: 'text-delta', index: 0, text: 'ok' },
        { type: 'block-end', index: 0, block: { type: 'text', text: 'ok' } },
        { type: 'usage', usage: { inputTokens: 2, outputTokens: 1 } },
        { type: 'finish', reason: { kind: 'stop' } },
      ];
      let index = 0;
      const iterator = {
        async next(): Promise<IteratorResult<StreamChunk>> {
          if (index >= chunks.length) return { done: true, value: undefined };
          return { done: false, value: chunks[index++] as StreamChunk };
        },
        return(): Promise<IteratorResult<StreamChunk>> {
          throw new Error('sync-return');
        },
      };
      return { [Symbol.asyncIterator]: () => iterator };
    }
    if (mode === 'hang-return') {
      const iterator = {
        async next(): Promise<IteratorResult<StreamChunk>> {
          return { done: true, value: undefined };
        },
        async return(): Promise<IteratorResult<StreamChunk>> {
          await new Promise(() => undefined);
          return { done: true, value: undefined };
        },
      };
      return { [Symbol.asyncIterator]: () => iterator };
    }
    return (async function* (): AsyncIterable<StreamChunk> {
      yield { type: 'block-start', index: 0, blockType: 'text' };
      yield { type: 'text-delta', index: 0, text: 'ok' };
      yield { type: 'block-end', index: 0, block: { type: 'text', text: 'ok' } };
      if (mode !== 'omit-usage') yield { type: 'usage', usage: { inputTokens: 2, outputTokens: 1 } };
      yield { type: 'finish', reason: { kind: 'stop' } };
    })();
  }
}

interface RecorderEvent { readonly kind: string; readonly detail: string }

class ControllableRecorder implements ContractApi.RequestRecorder {
  readonly claims: { taskId: string; epoch: number; purpose: string }[] = [];
  private readonly fences = new Map<string, number>();
  private minted = 0;

  private currentFence(taskId: string, epoch: number): number {
    const key = `${taskId}@${String(epoch)}`;
    const existing = this.fences.get(key);
    if (existing !== undefined) return existing;
    this.fences.set(key, 1);
    return 1;
  }

  supersede(taskId: string, epoch: number): number {
    const key = `${taskId}@${String(epoch)}`;
    const next = (this.fences.get(key) ?? 1) + 1;
    this.fences.set(key, next);
    return next;
  }

  async claim(request: { task: { taskId: string; epoch: number }; purpose: string }): Promise<import('../src/session-binding.js').ClaimReceipt> {
    this.claims.push({ taskId: request.task.taskId, epoch: request.task.epoch, purpose: request.purpose });
    this.minted += 1;
    return {
      claimId: `claim-${String(this.minted)}`, taskId: request.task.taskId, epoch: request.task.epoch,
      fence: this.currentFence(request.task.taskId, request.task.epoch),
      compositionRef: 'composition-h04', grantedAt: Date.now(),
    };
  }

  readonly events: RecorderEvent[] = [];
  private gate: { promise: Promise<void>; release: () => void; phase: 'reserve' | 'dispatch' } | undefined;
  private refusal: string | undefined;
  private entered: { promise: Promise<void>; resolve: () => void } | undefined;
  private dispatchEntered: { promise: Promise<void>; resolve: () => void } | undefined;
  armDispatchEntered(): Promise<void> {
    let resolve!: () => void;
    const promise = new Promise<void>((settle) => { resolve = settle; });
    this.dispatchEntered = { promise, resolve };
    return promise;
  }
  private settleGate: { promise: Promise<void>; release: () => void } | undefined;
  blockSettle(): void {
    let release!: () => void;
    const promise = new Promise<void>((resolve) => { release = resolve; });
    this.settleGate = { promise, release };
  }
  releaseSettle(): void { this.settleGate?.release(); this.settleGate = undefined; }
  failSettle = false;
  failMarkUnknown = false;
  nextId = 0;
  lastEstimate: ContractApi.RequestEstimate | undefined;

  block(phase: 'reserve' | 'dispatch' = 'reserve'): void {
    let release!: () => void;
    const promise = new Promise<void>((resolve) => { release = resolve; });
    this.gate = { promise, release, phase };
  }
  release(): void { this.gate?.release(); this.gate = undefined; }
  armEntered(): Promise<void> {
    let resolve!: () => void;
    const promise = new Promise<void>((settle) => { resolve = settle; });
    this.entered = { promise, resolve };
    return promise;
  }
  refuseWith(message: string): void { this.refusal = message.trim() === '' ? undefined : message; }
  forgive(): void { this.refusal = undefined; }

  async reserve(request: ContractApi.RequestReserveRequest, options?: { signal?: AbortSignal }): Promise<ContractApi.ReservationReceipt> {
    this.lastEstimate = request.estimate;
    this.events.push({ kind: 'reserve', detail: `seq=${String(request.identity.sequence)} session=${String(request.binding.sessionId)}` });
    this.entered?.resolve();
    if (this.gate?.phase === 'reserve') await this.waitForGate(options?.signal);
    if (options?.signal?.aborted === true) {
      throw new contract.RequestRejection('reserve-aborted', 'cancelled while reserving');
    }
    if (this.refusal !== undefined) {
      throw new contract.RequestRejection('reserve-refused', this.refusal);
    }
    this.nextId += 1;
    return {
      contractVersion: contract.REQUEST_CONTRACT_VERSION,
      reservationId: `res-${String(this.nextId)}`, requestId: `req-${String(this.nextId)}`,
      binding: request.binding, digest: request.digest, grantedAt: Date.now(),
    };
  }

  async dispatch(request: ContractApi.RequestDispatchRequest, options?: { signal?: AbortSignal }): Promise<ContractApi.DispatchReceipt> {
    this.events.push({ kind: 'dispatch', detail: `${request.digest.value.slice(0, 8)} session=${String(request.reservation.binding.sessionId)}` });
    this.dispatchEntered?.resolve();
    if (this.gate?.phase === 'dispatch') await this.waitForGate(options?.signal);
    if (options?.signal?.aborted === true) {
      throw new contract.RequestRejection('reserve-aborted', 'cancelled while dispatching');
    }
    return {
      contractVersion: contract.REQUEST_CONTRACT_VERSION,
      requestId: request.reservation.requestId, reservationId: request.reservation.reservationId,
      digest: request.digest, stage: 'dispatch-recorded', recordedAt: Date.now(),
    };
  }

  async settle(request: ContractApi.RequestSettleRequest): Promise<ContractApi.SettlementReceipt> {
    this.events.push({ kind: 'settle', detail: request.finish.kind });
    if (this.settleGate !== undefined) await this.settleGate.promise;
    if (this.failSettle) throw new Error('ledger unavailable');
    return {
      contractVersion: contract.REQUEST_CONTRACT_VERSION,
      requestId: request.requestId, settlementId: 'set-1',
      finish: request.finish, response: request.response, settledAt: Date.now(),
    };
  }

  async markUnknown(request: ContractApi.RequestMarkUnknownRequest): Promise<ContractApi.UnknownReceipt> {
    this.events.push({ kind: 'markUnknown', detail: request.reason });
    if (this.failMarkUnknown) throw new Error('ledger unavailable');
    return {
      contractVersion: contract.REQUEST_CONTRACT_VERSION,
      requestId: request.requestId, lastStage: request.lastStage, reason: request.reason,
      uncertainty: 'send-outcome-unknown', recordedAt: Date.now(),
    };
  }

  private async waitForGate(signal?: AbortSignal): Promise<void> {
    const gate = this.gate;
    if (gate === undefined) return;
    await new Promise<void>((resolve, reject) => {
      const onAbort = (): void => { reject(new contract.RequestRejection('reserve-aborted', 'cancelled while blocked')); };
      signal?.addEventListener('abort', onAbort, { once: true });
      gate.promise.then(
        () => { signal?.removeEventListener('abort', onAbort); resolve(); },
        (error: unknown) => { reject(error as Error); },
      );
    });
  }
}

let deployment: Context;
let accounting: typeof AccountingApi;
let contract: typeof ContractApi;
let bindings: import('../src/session-binding.js').SessionBindings;
let sessionModule: typeof import('../src/session-binding.js');
let dispatchModule: typeof import('../src/role-dispatch.js');
let root: import('../src/session-binding.js').BoundRoot;
let recorder: ControllableRecorder;
let privateRoot: string;
const handles: AgentHandle[] = [];
const diagnostics: { kind: string; detail: string; stage?: string; outcome?: string }[] = [];

const delegationTrace: Record<string, unknown>[] = [];
const childOptions = new Map<string, unknown>();
const resolvedRequests: Record<string, unknown>[] = [];

before(async () => {
  assert.equal(process.env.DSH_HOME, home, 'use the isolated launcher (npm run check:compat)');
  assert.ok(
    // Apply the complete original private-origin/cancellation acceptance to
    // the audited native-params variant; no assertion or case is omitted.
    ['0.2.0-rc.1+loop-origin.1', '0.2.0-rc.1+loop-origin.1-built',
      '0.2.0-rc.1+loop-origin.1+tool-choice.2'].includes(String(process.env.C2P_DSH_CANDIDATE)),
    `the launcher must pass this delivery's candidate: ${String(process.env.C2P_DSH_CANDIDATE)}`);
  privateRoot = mkdtempSync(path.join(runRoot, 'h04-cancel-'));
  mkdirSync(path.join(privateRoot, 'workspace'));
  const modules = path.join(privateRoot, 'node_modules');
  mkdirSync(path.join(modules, '@code2paper'), { recursive: true });
  symlinkSync(path.join(runtimeRoot, 'node_modules/@deepseek-ai'), path.join(modules, '@deepseek-ai'), 'dir');
  symlinkSync(stagedBundle, path.join(modules, '@code2paper/dsh-bundle'), 'dir');

  const bundle = await import(pathToFileURL(path.join(stagedBundle, 'lib/index.js')).href) as { name: string };
  assert.equal(bundle.name, 'code2paper-bridge');
  accounting = await import(pathToFileURL(path.join(stagedBundle, 'lib/request-accounting.js')).href) as typeof AccountingApi;
  contract = await import(pathToFileURL(path.join(stagedBundle, 'lib/request-contract.js')).href) as typeof ContractApi;
  sessionModule = await import(pathToFileURL(path.join(stagedBundle, 'lib/session-binding.js')).href) as typeof import('../src/session-binding.js');
  dispatchModule = await import(pathToFileURL(path.join(stagedBundle, 'lib/role-dispatch.js')).href) as typeof import('../src/role-dispatch.js');

  const profile = loadProfileDirectory('h04-cancel', profileDir, installAnchor);
  const configDir = path.join(privateRoot, 'cfg');
  mkdirSync(configDir, { recursive: true });
  const config = path.join(configDir, 'cordis.yml');
  writeFileSync(config, readFileSync(path.join(profileDir, 'cordis.yml')));
  const patches = [
    ...profile.layers.flatMap((layer) => layer.patches),
    ...profile.patches,
    ...loadOverlayPatches('h04-cancel', policyFile),
  ];
  deployment = await boot('h04-cancel', config, patches, (hostCtx: Context) => {
    provideCmdline(hostCtx, { args: ['--host', '127.0.0.1', '--port', '0', '--no-open'], exit: () => {} });
    hostCtx.on('agent/created', ({ agent }: { agent: { id: string; options: unknown } }) => {
      childOptions.set(agent.id, agent.options);
      return undefined;
    });
    hostCtx.on('agent/request', (payload: { agent: { id: string }; turn: number; step: number }, next: () => Promise<import('@deepseek-ai/dsh-llm').LlmCallConfig>) => {
      resolvedRequests.push({ agent: payload.agent.id, turn: payload.turn, step: payload.step });
      return next();
    });
    hostCtx.on('agent/error', (payload: any) => {
      delegationTrace.push({ kind: 'agent/error', payload: String(payload?.error?.stack ?? payload?.error) });
    });
  });
  deployment.llm.registerAdapter([MOCK_PROVIDER], new CountingAdapter());

  recorder = new ControllableRecorder();
  const bridge = deployment.get('code2paperBridge') as unknown as { hostGeneration: number };
  bindings = new sessionModule.SessionBindings({
    caller: { executionId: 'h04-execution', runId: 'h04-run', hostGeneration: bridge.hostGeneration },
    recorder: recorder as unknown as import('../src/session-binding.js').ClaimRecorder,
  });
  dispatchModule.registerCode2PaperSpawn(deployment, { bindings });
  root = await sessionModule.createBoundRootAgent(deployment, {
    bindings,
    sessionId: `h04-cancel-root-${runId}` as SessionId,
    task: { taskId: 'task-h04', epoch: 1 },
    cwd: path.join(privateRoot, 'workspace'),
  });

  accounting.installRequestAccounting(deployment, {
    bindings, recorder, route: MOCK_PROVIDER, purpose: 'writer',
    outputCap: { version: 'h04-test-cap/1', cap: () => 512 },
    diagnostics: (event) => { diagnostics.push({ ...event }); },
  });
});

after(async () => {
  const errors: unknown[] = [];
  recorder?.release();
  recorder?.releaseSettle();
  try { await root?.dispose(); } catch (error) { errors.push(error); }
  for (const handle of [...handles].reverse()) {
    try { await handle.dispose(); } catch (error) { errors.push(error); }
  }
  try { await deployment?.fiber.dispose(); } catch (error) { errors.push(error); }
  try { if (privateRoot !== undefined) rmSync(privateRoot, { recursive: true, force: true }); } catch (error) { errors.push(error); }
  if (errors.length > 0) throw new AggregateError(errors, 'H04 cancellation teardown failed');
});

/** An isolated runner: its own bindings, root, spawn provider and accounting install. */
interface IsolatedRunner {
  delegate(signal: AbortSignal): Promise<{ result: Promise<unknown>; dispose: () => Promise<void> }>;
  root: import('../src/session-binding.js').BoundRoot;
  readonly bindings: import('../src/session-binding.js').SessionBindings;
  dispose(): Promise<void>;
}

async function makeIsolatedRunner(
  label: string,
  cap: number | undefined,
  targetDeployment: Context = deployment,
  customRecorder: ControllableRecorder = recorder,
): Promise<IsolatedRunner> {
  const bridge = targetDeployment.get('code2paperBridge') as unknown as { hostGeneration: number };
  const runnerBindings = new sessionModule.SessionBindings({
    caller: { executionId: `h04-${label}`, runId: `h04-${label}-run`, hostGeneration: bridge.hostGeneration },
    recorder: customRecorder as unknown as import('../src/session-binding.js').ClaimRecorder,
  });
  const spawn = dispatchModule.registerCode2PaperSpawn(targetDeployment, {
    bindings: runnerBindings,
    providerName: `c2p-spawn-${label}`,
  });
  const runnerRoot = await sessionModule.createBoundRootAgent(targetDeployment, {
    bindings: runnerBindings,
    sessionId: `h04-${label}-root-${runId}` as SessionId,
    task: { taskId: `task-h04-${label}`, epoch: 1 },
    cwd: path.join(privateRoot, 'workspace'),
  });
  const runnerInstall = accounting.installRequestAccounting(targetDeployment, {
    bindings: runnerBindings,
    recorder: customRecorder,
    route: MOCK_PROVIDER,
    purpose: 'writer',
    outputCap: { version: 'h04-test-cap/1', cap: () => cap },
    isProtectedAgent: () => true,
    diagnostics: (event) => { diagnostics.push({ ...event }); },
  });
  return {
    root: runnerRoot,
    bindings: runnerBindings,
    async delegate(signal: AbortSignal) {
      const dispatched = await dispatchModule.dispatchRole(targetDeployment, {
        parent: runnerRoot.handle.agent,
        role: 'writer',
        prompt: [{ type: 'text', text: `isolated ${label}` }],
        signal,
        bindings: runnerBindings,
        providerName: spawn.providerName,
        agentOptions: { provider: MOCK_PROVIDER, model: MOCK_MODEL, maxTokens: 64 },
      });
      return { result: dispatched.run.result, dispose: () => dispatched.run.dispose() };
    },
    async dispose() {
      runnerInstall.dispose();
      await runnerRoot.dispose();
      spawn.dispose();
    },
  };
}

/** Delegate one bound child through the Host's narrow provider. */
async function delegate(signal: AbortSignal): Promise<{ result: Promise<unknown>; dispose: () => Promise<void> }> {
  const dispatched = await dispatchModule.dispatchRole(deployment, {
    parent: root.handle.agent,
    role: 'writer',
    prompt: [{ type: 'text', text: 'cancel probe' }],
    signal,
    bindings,
    agentOptions: { provider: MOCK_PROVIDER, model: MOCK_MODEL, maxTokens: 64 },
  });
  return { result: dispatched.run.result, dispose: () => dispatched.run.dispose() };
}

test('C0: a legal bound delegation reaches the seam and settles once (control)', async () => {
  const eventsBefore = recorder.events.length;
  const adaptersBefore = adapterDispatches.length;
  adapterLabel = 'c0-control';
  const delegation = await delegate(new AbortController().signal);
  const outcome = await delegation.result;
  await delegation.dispose();
  assert.equal(String((outcome as { stopReason?: string }).stopReason), 'completed');
  const events = recorder.events.slice(eventsBefore);
  assert.equal(adapterDispatches.length - adaptersBefore, 1,
    `the protected request must reach the adapter exactly once (run result: ${JSON.stringify(outcome)})`);
  assert.deepEqual(events.map((event) => event.kind), ['reserve', 'dispatch', 'settle']);
  assert.equal(events.at(-1)?.detail, 'settled');
});

test('C1: cancelling a blocked reservation dispatches nothing and settles nothing', async () => {
  const controller = new AbortController();
  recorder.block();
  const entered = recorder.armEntered();
  const before = adapterDispatches.length;
  const eventsBefore = recorder.events.length;

  const delegation = await delegate(controller.signal);
  await entered;
  assert.equal(adapterDispatches.length, before, 'no dispatch while the reservation is pending');
  assert.ok(!recorder.events.slice(eventsBefore).some((event) => event.kind === 'dispatch'));
  controller.abort();
  recorder.release();
  await delegation.result;
  await delegation.dispose();

  const events = recorder.events.slice(eventsBefore);
  assert.equal(adapterDispatches.length, before, 'no adapter dispatch may happen for a cancelled reservation');
  assert.ok(events.some((event) => event.kind === 'reserve'), 'reserve was attempted');
  assert.ok(!events.some((event) => event.kind === 'settle' && event.detail === 'settled'), 'never settles as success');
  assert.ok(!events.some((event) => event.kind === 'dispatch'), 'the send boundary is never entered');
  assert.ok(diagnostics.some((event) => event.kind === 'pre-dispatch-refused'),
    'the refusal is a named diagnostic');
});

test('C2: a refused reservation dispatches nothing', async () => {
  recorder.refuseWith('no budget');
  const before = adapterDispatches.length;
  const eventsBefore = recorder.events.length;
  const delegation = await delegate(new AbortController().signal);
  await delegation.result;
  await delegation.dispose();
  recorder.forgive();
  const events = recorder.events.slice(eventsBefore);
  assert.ok(events.some((event) => event.kind === 'reserve'),
    'the request must actually reach the seam, otherwise this proves nothing');
  assert.ok(!events.some((event) => event.kind === 'dispatch'), 'a refused reservation never dispatches');
  assert.ok(!events.some((event) => event.kind === 'settle'), 'a refused reservation never settles');
  assert.equal(adapterDispatches.length, before);
  assert.ok(diagnostics.some((event) => event.kind === 'pre-dispatch-refused' && event.detail === 'reserve-refused'));
});

test('C3: a healthy protected turn is dispatched once and settled once', async () => {
  const before = adapterDispatches.length;
  const eventsBefore = recorder.events.length;
  adapterLabel = 'c3-healthy';
  const delegation = await delegate(new AbortController().signal);
  await delegation.result;
  await delegation.dispose();

  const events = recorder.events.slice(eventsBefore);
  assert.equal(adapterDispatches.length - before, 1, 'exactly one dispatch');
  assert.deepEqual(
    events.filter((event) => event.kind === 'dispatch').length, 1, 'recorded before delegation once',
  );
  assert.deepEqual(
    events.filter((event) => event.kind === 'settle').map((event) => event.detail), ['settled'],
    'a finish + usage pair supports one settlement',
  );
  assert.equal(events.at(-1)?.kind, 'settle', 'the terminal record is last');
});

test('C4: a failing terminal record stays a named unsettled fact and is never retried', async () => {
  const eventsBefore = recorder.events.length;
  recorder.failSettle = true;
  adapterLabel = 'c4-failing-ledger';
  const delegation = await delegate(new AbortController().signal);
  await delegation.result;
  await delegation.dispose();
  recorder.failSettle = false;

  const events = recorder.events.slice(eventsBefore);
  assert.equal(events.filter((event) => event.kind === 'settle').length, 1, 'exactly one local attempt');
  assert.ok(diagnostics.some((event) => event.kind === 'terminal' && event.outcome === 'unsettled'),
    'the failure is reported as unsettled, not as success');
});

test('C5: quiescence claims name their resource scope', () => {
  const observable = {
    adapterStreams: resources.adapterStreams,
    managedSubprocesses: resources.managedSubprocesses,
    subprocessQuiescence: resources.managedSubprocesses === 0 ? 'not-applicable' : 'required',
    oracle: 'mock adapter observation for request end/cancel; waitForExit only for a managed subprocess',
  };
  assert.equal(observable.subprocessQuiescence, 'not-applicable');
  assert.equal(observable.managedSubprocesses, 0);
  assert.ok(observable.adapterStreams > 0, 'the adapter oracle must have been exercised');
  assert.equal(resources.note, 'no managed subprocess is started by this experiment');
});

test('C7: stop without usage is not a zero-cost settlement', async () => {
  adapterMode = 'omit-usage';
  const eventsBefore = recorder.events.length;
  const delegation = await delegate(new AbortController().signal);
  await delegation.result;
  await delegation.dispose();
  adapterMode = 'normal';
  const events = recorder.events.slice(eventsBefore);
  assert.ok(events.some((event) => event.kind === 'markUnknown' && event.detail === 'usage-missing'),
    `missing usage must stay missing: ${JSON.stringify(events)}`);
  assert.ok(!events.some((event) => event.kind === 'settle' && event.detail === 'settled'));
  assert.equal(recorder.lastEstimate?.source, 'utf8-byte-length');
  assert.equal(recorder.lastEstimate?.estimatorVersion, 'h04-stage-estimator/1');
  assert.ok((recorder.lastEstimate?.inputTokens ?? 0) > 0, 'the stage estimate is a measured byte length');
});

test('C8: an iterator return that does not finish is bounded and unsettled', async () => {
  const hanging = {
    async next(): Promise<IteratorResult<unknown>> {
      return { done: true, value: undefined };
    },
    async return(): Promise<IteratorResult<unknown>> {
      await new Promise(() => undefined);
      return { done: true, value: undefined };
    },
  };
  const started = Date.now();
  const cleanup = await accounting.boundedIteratorReturn(hanging);
  assert.equal(cleanup, 'timed-out');
  assert.ok(Date.now() - started < 1000, 'the return budget must expire instead of tracking the iterator');
  assert.equal(await accounting.boundedIteratorReturn(undefined), 'absent');
  const syncThrow = {
    async next(): Promise<IteratorResult<unknown>> { return { done: true, value: undefined }; },
    return(): Promise<IteratorResult<unknown>> { throw new Error('sync-return'); },
  };
  assert.equal(await accounting.boundedIteratorReturn(syncThrow), 'threw');
  const asyncThrow = {
    async next(): Promise<IteratorResult<unknown>> { return { done: true, value: undefined }; },
    async return(): Promise<IteratorResult<unknown>> { throw new Error('async-return'); },
  };
  assert.equal(await accounting.boundedIteratorReturn(asyncThrow), 'threw');

  adapterMode = 'hang-return';
  const eventsBefore = recorder.events.length;
  const delegation = await delegate(new AbortController().signal);
  await delegation.result;
  await delegation.dispose();
  adapterMode = 'normal';
  assert.ok(!recorder.events.slice(eventsBefore).some((event) => event.kind === 'settle' && event.detail === 'settled'));
});

test('C9: two live children each settle once, and a copied signal cannot spend the preparation', async () => {
  adapterMode = 'normal';
  let releaseHold: (() => void) | undefined;
  const hold = new Promise<void>((resolve) => { releaseHold = resolve; });
  let stolen: { signal?: AbortSignal; sessionId?: string } = {};
  const stop = deployment.on('agent/request', ((
    payload: { signal?: AbortSignal; agent?: { id: string } },
    next: () => Promise<unknown>,
  ) => {
    if (stolen.signal === undefined && payload.signal !== undefined) {
      stolen = { signal: payload.signal, sessionId: payload.agent?.id };
      return hold.then(() => next());
    }
    return next();
  }) as never);
  const before = adapterDispatches.length;
  const first = delegate(new AbortController().signal);
  try {
    const visible = await new Promise<typeof stolen>((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('preparation was not observed')), 5000);
      const wait = (): void => {
        if (stolen.signal !== undefined) {
          clearTimeout(timer);
          resolve(stolen);
          return;
        }
        setTimeout(wait, 10);
      };
      wait();
    });
    const impersonated: GenerateOptions = {
      provider: MOCK_PROVIDER,
      model: MOCK_MODEL,
      maxTokens: 64,
      messages: [{ role: 'user', content: [{ type: 'text', text: 'stolen' }] }],
      sessionId: visible.sessionId as SessionId,
      signal: visible.signal,
    };
    const chunks: StreamChunk[] = [];
    for await (const chunk of deployment.llm.stream(impersonated)) chunks.push(chunk);
    assert.equal(adapterDispatches.length, before, 'a copied signal during preparation must not reach the adapter');
    assert.ok(chunks.some((chunk) => chunk.type === 'finish' && typeof chunk.reason !== 'string' && chunk.reason.kind === 'error'));
    releaseHold?.();
    stop();
    const second = delegate(new AbortController().signal);
    const [left, right] = await Promise.all([first, second]);
    await left.result;
    await right.result;
    await left.dispose();
    await right.dispose();
    const sessions = new Set(adapterDispatches.slice(before).map((row) => row.sessionId));
    assert.equal(sessions.size, 2, 'the two children are metered as two dispatches');
    assert.equal(adapterDispatches.length - before, 2);
  } finally {
    releaseHold?.();
    stop();
  }
});

test('C10: a public withInitiator cannot spend a prepare wait', async () => {
  adapterMode = 'normal';
  let releasePrepare!: () => void;
  prepareHold = new Promise<void>((resolve) => { releasePrepare = resolve; });
  const entered = new Promise<void>((resolve) => { prepareEntered = resolve; });
  let seen: { agent: { id: string }; signal: AbortSignal } | undefined;
  const stop = deployment.on('agent/request', ((
    payload: { agent: { id: string }; signal: AbortSignal },
    next: () => Promise<unknown>,
  ) => {
    seen = payload;
    return next();
  }) as never);
  const before = adapterDispatches.length;
  const eventsBefore = recorder.events.length;
  const delegation = delegate(new AbortController().signal);
  try {
    await entered;
    assert.ok(seen !== undefined);
    const agents = deployment.agents as unknown as {
      withInitiator<T>(agent: { id: string }, operation: () => T): T;
    };
    const chunks: StreamChunk[] = [];
    await agents.withInitiator(seen.agent, async () => {
      for await (const chunk of deployment.llm.stream({
        provider: MOCK_PROVIDER,
        model: MOCK_MODEL,
        maxTokens: 8,
        messages: [{ role: 'user', content: [{ type: 'text', text: 'stolen-prepare' }] }],
        sessionId: seen!.agent.id as SessionId,
        signal: seen!.signal,
      })) chunks.push(chunk);
    });
    assert.equal(adapterDispatches.length, before, 'the bare prepare-wait request must not reach the adapter');
    assert.ok(chunks.some((chunk) => chunk.type === 'finish' && typeof chunk.reason !== 'string' && chunk.reason.kind === 'error'));
    assert.equal(recorder.events.length, eventsBefore, 'a refused steal must not reserve');
    releasePrepare();
    prepareHold = undefined;
    const outcome = await delegation;
    await outcome.result;
    await outcome.dispose();
    assert.equal(adapterDispatches.length - before, 1, 'the original child still reaches the adapter once');
    const events = recorder.events.slice(eventsBefore);
    assert.equal(events.filter((event) => event.kind === 'reserve').length, 1);
    assert.equal(events.filter((event) => event.kind === 'dispatch').length, 1);
    assert.equal(events.filter((event) => event.kind === 'settle').length, 1);
  } finally {
    releasePrepare();
    prepareHold = undefined;
    prepareEntered = undefined;
    stop();
  }
});

test('C11: one child preparing does not reject a sibling', async () => {
  adapterMode = 'normal';
  let releaseA!: () => void;
  const holdA = new Promise<void>((resolve) => { releaseA = resolve; });
  let held = false;
  const stop = deployment.on('agent/request', ((
    _payload: { signal?: AbortSignal },
    next: () => Promise<unknown>,
  ) => {
    if (!held) {
      held = true;
      return holdA.then(() => next());
    }
    return next();
  }) as never);
  const before = adapterDispatches.length;
  const a = delegate(new AbortController().signal);
  try {
    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('child A did not enter preparation')), 5000);
      const wait = (): void => {
        if (held) { clearTimeout(timer); resolve(); return; }
        setTimeout(wait, 10);
      };
      wait();
    });
    const b = await delegate(new AbortController().signal);
    await b.result;
    await b.dispose();
    assert.equal(adapterDispatches.length - before, 1, 'child B must dispatch while A is still preparing');
    releaseA();
    const aRun = await a;
    await aRun.result;
    await aRun.dispose();
    assert.equal(adapterDispatches.length - before, 2, 'child A still dispatches once after it is released');
  } finally {
    releaseA();
    stop();
  }
});

test('C13: a public listener re-entering with the real request object cannot take the origin', async () => {
  adapterMode = 'normal';
  let attacked = false;
  let nestedError = false;
  let nestedCode = '';
  let stop: (() => void) | undefined;
  const before = adapterDispatches.length;
  const eventsBefore = recorder.events.length;
  try {
    const delegationPromise = delegate(new AbortController().signal);
    await new Promise<void>((resolve) => {
      stop = deployment.on('llm/stream', ((request: GenerateOptions, next: () => AsyncIterable<StreamChunk>) => {
        if (attacked) return next();
        attacked = true;
        void (async () => {
          try {
            for await (const chunk of deployment.llm.stream(request)) {
              if (chunk.type === 'finish' && typeof chunk.reason !== 'string' && chunk.reason.kind === 'error') {
                nestedError = true;
                nestedCode = String(chunk.reason.failure.code);
              }
            }
          } catch (error) {
            // loop-origin.1 (2026-10-02 repair): there is no public consume to
            // pre-empt, so a same-request re-entry is isolated from the outer
            // origin by the runtime and refused by the Host middleware by name.
            nestedError = true;
            nestedCode = String((error as { code?: string }).code ?? '');
          }
        })();
        resolve();
        return next();
      }) as never);
    });
    const delegation = await delegationPromise;
    await delegation.result;
    await delegation.dispose();
    assert.ok(attacked, 'the public listener must have observed the real dispatch');
    assert.ok(nestedError, 'the re-entered bare request must be refused by name');
    assert.equal(nestedCode, 'dispatch_origin_unproven', 'the re-entry is refused by name with zero reserve/adapter');
    assert.equal(adapterDispatches.length - before, 1, 'only the legal request reaches the adapter');
    const events = recorder.events.slice(eventsBefore);
    assert.equal(events.filter((event) => event.kind === 'reserve').length, 1);
    assert.equal(events.filter((event) => event.kind === 'dispatch').length, 1);
    assert.equal(events.filter((event) => event.kind === 'settle' && event.detail === 'settled').length, 1);
  } finally {
    stop?.();
  }
});

test('C14: a real NO_ADAPTER fallback cannot be stolen by same-signal copies', async () => {
  adapterMode = 'no-adapter-once';
  let attacked = false;
  const nested: { full: boolean; drift: boolean; delayed: boolean } = { full: true, drift: true, delayed: true };
  let stashed: GenerateOptions | undefined;
  let seenAgent: { id: string } | undefined;
  let stop: (() => void) | undefined;
  let stopObserve: (() => void) | undefined;
  let attackDone: Promise<void> = Promise.resolve();
  const before = adapterDispatches.length;
  const eventsBefore = recorder.events.length;
  try {
    stopObserve = deployment.on('agent/request', ((payload: { agent: { id: string } }, next: () => Promise<unknown>) => {
      if (seenAgent === undefined) seenAgent = payload.agent;
      return next();
    }) as never);
    const delegationPromise = delegate(new AbortController().signal);
    await new Promise<void>((resolve) => {
      stop = deployment.on('llm/stream', ((request: GenerateOptions, next: () => AsyncIterable<StreamChunk>) => {
        if (attacked) return next();
        attacked = true;
        stashed = request;
        const refusedStream = async (run: () => Promise<StreamChunk[]>): Promise<boolean> => {
          try {
            const chunks = await run();
            return chunks.some((chunk) => chunk.type === 'finish' && typeof chunk.reason !== 'string' && chunk.reason.kind === 'error');
          } catch (error) {
            // loop-origin.1: while the origin scope is alive the runtime refuses
            // any publicly initiated re-entry synchronously, by name.
            return error instanceof LlmError && error.code === 'DISPATCH_ORIGIN_CONSUMED';
          }
        };
        const collect = async (stream: AsyncIterable<StreamChunk>): Promise<StreamChunk[]> => {
          const chunks: StreamChunk[] = [];
          for await (const chunk of stream) chunks.push(chunk);
          return chunks;
        };
        attackDone = (async () => {
          const agents = deployment.agents as unknown as {
            withInitiator<T>(agent: { id: string }, operation: () => Promise<T>): Promise<T>;
          };
          // The QA probe shape: the public listener holds the exact Agent and
          // signal, and re-enters through the public setter with a full copy.
          const fullCopy: GenerateOptions = { ...request };
          nested.full = await refusedStream(() =>
            agents.withInitiator(seenAgent!, async () => collect(deployment.llm.stream(fullCopy))));
          const drift: GenerateOptions = {
            ...request,
            messages: [{ role: 'user', content: [{ type: 'text', text: 'different material' }] }],
          };
          nested.drift = await refusedStream(() =>
            agents.withInitiator(seenAgent!, async () => collect(deployment.llm.stream(drift))));
        })();
        resolve();
        return next();
      }) as never);
    });
    const delegation = await delegationPromise;
    const outcome = await delegation.result;
    await delegation.dispose();
    await attackDone;
    assert.ok(attacked);
    assert.ok(nested.full && nested.drift, `same-signal copies must be refused: ${JSON.stringify(nested)}`);
    assert.equal(String((outcome as { stopReason?: string }).stopReason), 'completed',
      `the legal fallback must still complete: ${JSON.stringify(outcome)}`);
    assert.equal(adapterDispatches.length - before, 1, 'only the legal fallback reaches the adapter');
    // Delayed replay after the legal extent: nothing left to claim.
    if (stashed !== undefined) {
      const lateChunks: StreamChunk[] = [];
      for await (const chunk of deployment.llm.stream({ ...stashed })) lateChunks.push(chunk);
      nested.delayed = lateChunks.some((chunk) => chunk.type === 'finish' && typeof chunk.reason !== 'string' && chunk.reason.kind === 'error');
      assert.ok(nested.delayed, 'a delayed same-signal replay must be refused');
    }
    const events = recorder.events.slice(eventsBefore);
    assert.equal(events.filter((event) => event.kind === 'reserve').length, 1);
    assert.equal(events.filter((event) => event.kind === 'settle' && event.detail === 'settled').length, 1);
  } finally {
    adapterMode = 'normal';
    stop?.();
    stopObserve?.();
  }
});

test('C14b: a genuinely absent adapter stays a named failure and stolen handles carry no origin', async () => {
  adapterMode = 'no-adapter-always';
  const before = adapterDispatches.length;
  const eventsBefore = recorder.events.length;
  try {
    const delegation = await delegate(new AbortController().signal);
    const outcome = await delegation.result;
    await delegation.dispose();
    // The loop's fallback handle dispatches through the origin run; the
    // genuinely absent adapter fails by name at the adapter boundary.
    assert.equal(adapterDispatches.length, before, 'a missing adapter is never simulated');
    const afterLegalAdapter = adapterDispatches.length;
    const afterLegalEvents = recorder.events.length;
    const events = recorder.events.slice(eventsBefore);
    assert.ok(events.some((event) => event.kind === 'reserve'), `the fallback dispatch was accounted: ${JSON.stringify(events)}`);
    assert.ok(!events.some((event) => event.kind === 'settle' && event.detail === 'settled'),
      `a failed fallback never settles as success: ${JSON.stringify(events)}`);
    assert.notEqual(String((outcome as { stopReason?: string }).stopReason), 'completed',
      `the child must not complete without an adapter: ${JSON.stringify(outcome)}`);
    // An extension's own prepareCall also resolves with a handle, but the
    // handle carries no dispatch origin: its dispatch is refused with zero
    // reserve and zero adapter.
    const chunks: StreamChunk[] = [];
    for await (const chunk of deployment.llm.stream({
      provider: MOCK_PROVIDER, model: MOCK_MODEL, maxTokens: 64,
      messages: [{ role: 'user', content: [{ type: 'text', text: 'stolen handle' }] }],
    } as GenerateOptions)) chunks.push(chunk);
    assert.ok(chunks.some((chunk) => chunk.type === 'finish' && typeof chunk.reason !== 'string' && chunk.reason.kind === 'error'),
      `a stolen handle must not dispatch: ${JSON.stringify(chunks)}`);
    assert.equal(adapterDispatches.length, afterLegalAdapter, 'a stolen handle never reaches the adapter');
    assert.equal(recorder.events.length, afterLegalEvents, 'a stolen handle never reserves');
  } finally {
    adapterMode = 'normal';
  }
});

test('C15: external material drift after the dispatch claim cannot dispatch', async () => {
  adapterMode = 'normal';
  let observed: GenerateOptions | undefined;
  let stop: (() => void) | undefined;
  const before = adapterDispatches.length;
  const eventsBefore = recorder.events.length;
  const diagnosticsBefore = diagnostics.length;
  const runner = await makeIsolatedRunner('drift', 512);
  recorder.blockSettle();
  assert.ok(diagnosticsBefore >= 0);
  try {
    const delegationPromise = runner.delegate(new AbortController().signal);
    await new Promise<void>((resolve) => {
      stop = deployment.on('llm/stream', ((request: GenerateOptions, next: () => AsyncIterable<StreamChunk>) => {
        if (observed === undefined) observed = request;
        resolve();
        return next();
      }) as never);
    });
    const delegation = await delegationPromise;
    await new Promise<void>((resolve, reject) => {
      const started = Date.now();
      const wait = (): void => {
        if (recorder.events.slice(eventsBefore).some((event) => event.kind === 'settle')) {
          resolve();
          return;
        }
        if (Date.now() - started > 5000) {
          reject(new Error(`the settlement wait was never entered: ${JSON.stringify(recorder.events.slice(eventsBefore))}`));
          return;
        }
        setTimeout(wait, 10);
      };
      wait();
    });
    const settleIndex = recorder.events.slice(eventsBefore).findIndex((event) => event.kind === 'settle');
    assert.ok(settleIndex >= 0, 'the settlement wait must be observable');
    assert.ok(observed !== undefined);
    assert.ok(Object.isFrozen(observed.messages), 'the runtime freezes the request material, so in-place drift is not an external capability');
    const drifted: GenerateOptions = {
      ...observed,
      messages: [{ role: 'user', content: [{ type: 'text', text: 'drifted material' }] }],
    };
    const driftChunks: StreamChunk[] = [];
    for await (const chunk of deployment.llm.stream(drifted)) driftChunks.push(chunk);
    assert.ok(driftChunks.some((chunk) => chunk.type === 'finish' && typeof chunk.reason !== 'string' && chunk.reason.kind === 'error'),
      `drifted material must be refused at the entry: ${JSON.stringify(driftChunks)}`);
    assert.equal(adapterDispatches.length, before + 1, 'only the legal request reached the adapter');
    recorder.releaseSettle();
    await delegation.result;
    await delegation.dispose();
    const events = recorder.events.slice(eventsBefore);
    assert.ok(events.some((event) => event.kind === 'settle' && event.detail === 'settled'),
      `the legal request still completes: ${JSON.stringify(events)}`);
    assert.equal(events.filter((event) => event.kind === 'settle').length, 1);
  } finally {
    recorder.releaseSettle();
    stop?.();
    await runner.dispose();
  }
});

test('C16: an abort during the dispatch wait reaches no adapter and settles nothing', async () => {
  adapterMode = 'normal';
  const before = adapterDispatches.length;
  const eventsBefore = recorder.events.length;
  const diagnosticsBefore = diagnostics.length;
  recorder.block('dispatch');
  const entered = recorder.armDispatchEntered();
  const runner = await makeIsolatedRunner('abort-dispatch', 512);
  const controller = new AbortController();
  const delegation = await runner.delegate(controller.signal);
  try {
    await entered;
    controller.abort();
    recorder.release();
    await delegation.result;
  } finally {
    recorder.release();
  }
  await delegation.dispose();
  await runner.dispose();
  assert.equal(adapterDispatches.length, before, 'an aborted dispatch wait never reaches the adapter');
  const events = recorder.events.slice(eventsBefore);
  assert.ok(events.some((event) => event.kind === 'dispatch'), 'the dispatch receipt wait really happened');
  assert.ok(!events.some((event) => event.kind === 'settle' && event.detail === 'settled'),
    `an aborted dispatch must not settle: events=${JSON.stringify(events)}`);
  assert.ok(diagnostics.slice(diagnosticsBefore).some((event) => event.detail === 'reserve-aborted'),
    `expected a named abort after the dispatch wait: ${JSON.stringify(diagnostics.slice(diagnosticsBefore))}`);
});

test('C17: a fence advance during the reserve wait reaches no adapter', async () => {
  adapterMode = 'normal';
  const before = adapterDispatches.length;
  const eventsBefore = recorder.events.length;
  const diagnosticsBefore = diagnostics.length;
  recorder.block('reserve');
  const entered = recorder.armEntered();
  const runner = await makeIsolatedRunner('fence-reserve', 512);
  const delegation = await runner.delegate(new AbortController().signal);
  try {
    await entered;
    recorder.supersede('task-h04-fence-reserve', 1);
    await runner.bindings.claim({ task: { taskId: 'task-h04-fence-reserve', epoch: 1 }, purpose: 'root' });
    recorder.release();
    await delegation.result;
  } finally {
    recorder.release();
  }
  await delegation.dispose();
  await runner.dispose();
  assert.equal(adapterDispatches.length, before);
  const events = recorder.events.slice(eventsBefore);
  assert.ok(events.some((event) => event.kind === 'reserve'));
  assert.ok(!events.some((event) => event.kind === 'dispatch'), `a superseded fence never dispatches: ${JSON.stringify(events)}`);
  assert.ok(!events.some((event) => event.kind === 'settle' && event.detail === 'settled'));
  assert.ok(diagnostics.slice(diagnosticsBefore).some((event) => event.detail === 'stale-binding'),
    `expected a named stale binding: ${JSON.stringify(diagnostics.slice(diagnosticsBefore))}`);
});

test('C18: an unestablished output cap refuses the request before any receipt', async () => {
  adapterMode = 'normal';
  const before = adapterDispatches.length;
  const eventsBefore = recorder.events.length;
  const diagnosticsBefore = diagnostics.length;
  const runner = await makeIsolatedRunner('no-cap', undefined);
  try {
    const delegation = await runner.delegate(new AbortController().signal);
    await delegation.result;
    await delegation.dispose();
    assert.equal(adapterDispatches.length, before, 'an unestablished cap never reaches the adapter');
    assert.equal(recorder.events.length, eventsBefore, `no receipt may exist without a cap: ${JSON.stringify(recorder.events.slice(eventsBefore))}`);
    assert.ok(diagnostics.slice(diagnosticsBefore).some((event) => event.kind === 'pre-dispatch-refused' && event.detail === 'contract-unsupported'),
      `expected a named cap refusal: ${JSON.stringify(diagnostics.slice(diagnosticsBefore))}`);
  } finally {
    await runner.dispose();
  }
});

test('C12: a synchronous iterator return after settle is a named unsettled cleanup', async () => {
  adapterMode = 'normal';
  const stop = deployment.on('agent/created', (({ agent }: { agent: { ctx: { on: Function } } }) => {
    agent.ctx.on('llm/stream', (_request: unknown, next: () => AsyncIterable<StreamChunk>) => {
      const inner = next();
      return {
        [Symbol.asyncIterator]() {
          const iterator = inner[Symbol.asyncIterator]();
          return {
            next: () => iterator.next(),
            return(): Promise<IteratorResult<StreamChunk>> {
              throw new Error('sync-return');
            },
          };
        },
      };
    });
    return undefined;
  }) as never);
  const eventsBefore = recorder.events.length;
  const diagnosticsBefore = diagnostics.length;
  try {
    const delegation = await delegate(new AbortController().signal);
    await delegation.result;
    await delegation.dispose();
  } finally {
    stop();
  }
  const events = recorder.events.slice(eventsBefore);
  assert.equal(events.filter((event) => event.kind === 'settle' && event.detail === 'settled').length, 1,
    `settlement must happen once: ${JSON.stringify(events)}`);
  assert.ok(diagnostics.slice(diagnosticsBefore).some((event) => event.detail === 'iterator-return-threw' && event.outcome === 'unsettled'),
    `cleanup must be named: ${JSON.stringify(diagnostics.slice(diagnosticsBefore))}`);
});

test('C12b: an async return rejection and an iteration throw both end in named facts', async () => {
  const wrapReturn = (rejectAsync: boolean): (() => void) => deployment.on('agent/created', (({ agent }: { agent: { ctx: { on: Function } } }) => {
    agent.ctx.on('llm/stream', (_request: unknown, next: () => AsyncIterable<StreamChunk>) => {
      const inner = next();
      return {
        [Symbol.asyncIterator]() {
          const iterator = inner[Symbol.asyncIterator]();
          return {
            next: () => iterator.next(),
            return(): Promise<IteratorResult<StreamChunk>> {
              if (!rejectAsync) throw new Error('sync-return');
              return new Promise((_resolve, reject) => { setTimeout(() => reject(new Error('async-return')), 5); });
            },
          };
        },
      };
    });
    return undefined;
  }) as never);
  for (const rejectAsync of [false, true]) {
    const stop = wrapReturn(rejectAsync);
    const eventsBefore = recorder.events.length;
    const diagnosticsBefore = diagnostics.length;
    try {
      const delegation = await delegate(new AbortController().signal);
      await delegation.result;
      await delegation.dispose();
    } finally {
      stop();
    }
    const events = recorder.events.slice(eventsBefore);
    assert.ok(events.some((event) => event.kind === 'settle' && event.detail === 'settled'),
      `settlement still happens once (${String(rejectAsync)}): ${JSON.stringify(events)}`);
    assert.equal(events.filter((event) => event.kind === 'settle').length, 1,
      `the cleanup failure must not re-settle (${String(rejectAsync)})`);
    assert.ok(diagnostics.slice(diagnosticsBefore).some((event) => event.detail === 'iterator-return-threw' && event.outcome === 'unsettled'),
      `cleanup must be named (${String(rejectAsync)}): ${JSON.stringify(diagnostics.slice(diagnosticsBefore))}`);
  }

  adapterMode = 'fail-next';
  const eventsBefore = recorder.events.length;
  try {
    const delegation = await delegate(new AbortController().signal);
    await delegation.result;
    await delegation.dispose();
  } finally {
    adapterMode = 'normal';
  }
  const events = recorder.events.slice(eventsBefore);
  assert.ok(events.some((event) => event.kind === 'markUnknown' && event.detail === 'provider-error-usage-missing'),
    `an iteration error with no provider usage must retain uncertainty: ${JSON.stringify(events)}`);
  assert.equal(events.filter((event) => event.kind === 'markUnknown').length, 1);
  assert.equal(events.filter((event) => event.kind === 'settle').length, 0);
});

test('C6: a fence advance during dispatch reaches no adapter', async () => {
  adapterMode = 'normal';
  const before = adapterDispatches.length;
  const eventsBefore = recorder.events.length;
  const diagnosticsBefore = diagnostics.length;
  recorder.block('dispatch');
  const entered = recorder.armDispatchEntered();
  const runner = await makeIsolatedRunner('fence-dispatch', 512);
  const delegation = await runner.delegate(new AbortController().signal);
  try {
    await entered;
    recorder.supersede('task-h04-fence-dispatch', 1);
    await runner.bindings.claim({ task: { taskId: 'task-h04-fence-dispatch', epoch: 1 }, purpose: 'root' });
    recorder.release();
    await delegation.result;
  } finally {
    recorder.release();
  }
  await delegation.dispose();
  await runner.dispose();
  assert.equal(adapterDispatches.length, before, 'the post-dispatch recheck must run before the adapter');
  const events = recorder.events.slice(eventsBefore);
  assert.ok(events.some((event) => event.kind === 'dispatch'), 'dispatch was awaited');
  assert.ok(!events.some((event) => event.kind === 'settle' && event.detail === 'settled'),
    `a superseded dispatch must not settle: ${JSON.stringify(events)}`);
  assert.ok(diagnostics.slice(diagnosticsBefore).some((event) => event.detail === 'stale-binding'),
    `expected a stale binding after the dispatch wait: ${JSON.stringify(diagnostics.slice(diagnosticsBefore))}`);
});
// --------------------------------------------------------------------------- //
// loop-origin.1 acceptance rework probes (stage_loop_origin_acceptance_20261001)
// --------------------------------------------------------------------------- //

const OTHER_PROVIDER = 'c2p-h04-other-mock';
const OTHER_MODEL = 'h04-other-model';

/** A plain second adapter whose dispatches are counted separately. */
class OtherAdapter extends LlmAdapter {
  readonly calls: string[] = [];
  override providerInfo(provider: string): { id: string; name: string } {
    return { id: provider, name: `h04 other mock (${provider})` };
  }
  override async listModels(): Promise<never[]> { return []; }
  override async resolveModel(provider: string, model: string) {
    return { provider, id: model, name: `H04 other ${model}`, context: { contextWindow: 8192 }, defaultMaxTokens: 512 };
  }
  override async prepareCall(provider: string, model: string) {
    return { model: await this.resolveModel(provider, model), stream: (options: GenerateOptions) => this.stream(options) };
  }
  override async *stream(options: GenerateOptions): AsyncIterable<StreamChunk> {
    this.calls.push(String(options.sessionId));
    yield { type: 'block-start', index: 0, blockType: 'text' };
    yield { type: 'text-delta', index: 0, text: 'ok' };
    yield { type: 'usage', usage: { inputTokens: 3, outputTokens: 2 } };
    yield { type: 'finish', reason: { kind: 'stop' } };
  }
}

let otherAdapter: OtherAdapter | undefined;

test('C19: public dispatches initiated inside a live loop scope reach their own provider', async () => {
  adapterMode = 'normal';
  otherAdapter = new OtherAdapter();
  deployment.llm.registerAdapter([OTHER_PROVIDER], otherAdapter);
  const before = adapterDispatches.length;
  const otherBefore = otherAdapter.calls.length;
  const eventsBefore = recorder.events.length;
  let attackDone: Promise<void> = Promise.resolve();
  try {
    const delegationPromise = delegate(new AbortController().signal);
    await new Promise<void>((resolve) => {
      const stop = deployment.on('llm/stream', ((request: GenerateOptions, next: () => AsyncIterable<StreamChunk>) => {
        if (request.provider !== MOCK_PROVIDER) return next();
        // Inside the loop's live origin scope: three public entries to another
        // provider. None of them may inherit or trip over the outer origin
        // (acceptance LO-1); each is ordinary public traffic on its own route.
        const publicConfig: GenerateOptions = {
          provider: OTHER_PROVIDER, model: OTHER_MODEL, maxTokens: 64,
          messages: [{ role: 'user', content: [{ type: 'text', text: 'in-loop public dispatch' }] }],
        };
        attackDone = (async () => {
          const settle = async (stream: AsyncIterable<StreamChunk>): Promise<boolean> => {
            let sawStop = false;
            for await (const chunk of stream) {
              if (chunk.type === 'finish' && typeof chunk.reason !== 'string' && chunk.reason.kind === 'stop') sawStop = true;
              if (chunk.type === 'finish' && typeof chunk.reason !== 'string' && chunk.reason.kind === 'error') return false;
            }
            return sawStop;
          };
          // (a) the public llm.stream entry
          const directOk = await settle(deployment.llm.stream({ ...publicConfig }));
          // (b) a prepared handle obtained before the loop's dispatch
          const preHandle = await deployment.llm.prepareCall({ ...publicConfig }, new AbortController().signal);
          const preOk = await settle(preHandle.stream({ ...publicConfig }));
          // (c) a handle from an on-the-spot public prepareCall
          const spotHandle = await deployment.llm.prepareCall({ ...publicConfig }, new AbortController().signal);
          const spotOk = await settle(spotHandle.stream({ ...publicConfig }));
          if (!directOk || !preOk || !spotOk) throw new Error('an in-loop public dispatch did not complete');
        })().catch((error) => { throw error; });
        void attackDone;
        resolve();
        return next();
      }) as never);
      void stop;
    });
    const delegation = await delegationPromise;
    const outcome = await delegation.result;
    await delegation.dispose();
    await attackDone;
    assert.equal(otherAdapter.calls.length - otherBefore, 3,
      `all three public entries must reach the other provider exactly once: ${JSON.stringify(otherAdapter.calls)}`);
    assert.equal(adapterDispatches.length - before, 1, 'the legal child dispatch reaches the protected adapter once');
    const events = recorder.events.slice(eventsBefore);
    assert.deepEqual(events.map((event) => event.kind), ['reserve', 'dispatch', 'settle'],
      `only the legal child is accounted: ${JSON.stringify(events)}`);
    assert.equal(String((outcome as { stopReason?: string }).stopReason), 'completed',
      `the legal child must still complete: ${JSON.stringify(outcome)}`);
  } finally {
    otherAdapter = undefined;
  }
});

test('C20: public prepareCall keeps the original NO_ADAPTER semantics while the loop fallback stays legal', async () => {
  // (a) a genuinely absent adapter: the PUBLIC prepareCall still rejects by
  // name (acceptance LO-2) — no fallback handle is minted for public callers.
  adapterMode = 'no-adapter-always';
  const publicConfig: GenerateOptions = {
    provider: MOCK_PROVIDER, model: MOCK_MODEL, maxTokens: 64,
    messages: [{ role: 'user', content: [{ type: 'text', text: 'public prepare' }] }],
  };
  await assert.rejects(
    deployment.llm.prepareCall({ ...publicConfig }, new AbortController().signal),
    (error: unknown) => error instanceof LlmError && error.code === 'NO_ADAPTER',
    'the public prepareCall must keep the original NO_ADAPTER rejection',
  );

  // (b) a one-shot adapter failure: the loop's fallback dispatch (through the
  // public llm.stream inside the loop's origin run) is admitted exactly once
  // and completes legally; the public surface never sees a fallback handle.
  adapterMode = 'no-adapter-once';
  const before = adapterDispatches.length;
  const eventsBefore = recorder.events.length;
  try {
    const delegation = await delegate(new AbortController().signal);
    const outcome = await delegation.result;
    await delegation.dispose();
    assert.equal(adapterDispatches.length - before, 1, 'the legal fallback dispatch reaches the adapter once');
    const events = recorder.events.slice(eventsBefore);
    assert.deepEqual(events.map((event) => event.kind), ['reserve', 'dispatch', 'settle'],
      `the fallback dispatch is accounted exactly once: ${JSON.stringify(events)}`);
    assert.equal(String((outcome as { stopReason?: string }).stopReason), 'completed',
      `the legal fallback must complete: ${JSON.stringify(outcome)}`);
    const handle = await deployment.llm.prepareCall({ ...publicConfig }, new AbortController().signal);
    assert.ok(handle !== undefined, 'a healthy public prepareCall still returns a handle');
  } finally {
    adapterMode = 'normal';
  }
});

test('C21: a public async-hook observer cannot consume, mint or preempt the loop origin', async () => {
  // The QA LO-4-PRECONSUME shape: an observer registers a public async hook
  // and, at every hook, uses ONLY the public surface — the read-only peek,
  // the entry-acknowledgement take, and a public dispatch claiming the
  // protected session. The legal child must complete untouched.
  adapterMode = 'normal';
  const { createHook } = await import('node:async_hooks');
  const loopMod = (await import('@deepseek-ai/dsh-agent-loop')) as unknown as {
    peekLoopDispatchOrigin?: () => { readonly sessionId: string; readonly signal: AbortSignal } | undefined;
    admitLoopDispatchOrigin?: (capability: unknown) => boolean;
  };
  const llmMod = (await import('@deepseek-ai/dsh-llm')) as unknown as {
    runLoopDispatch?: (options: GenerateOptions, preparedCall: unknown, capability: unknown) => AsyncIterable<StreamChunk>;
  };
  const before = adapterDispatches.length;
  const eventsBefore = recorder.events.length;
  let hookSeesOrigin = 0;
  let takeSucceeded = 0;
  let attackedSession = '';
  let attackDone: Promise<void> = Promise.resolve();
  let attackChunks: StreamChunk[] = [];
  const hook = createHook({
    init() {
      const peek = loopMod.peekLoopDispatchOrigin;
      const admit = loopMod.admitLoopDispatchOrigin;
      if (typeof peek !== 'function' || typeof admit !== 'function') return;
      const origin = peek();
      if (origin === undefined) return;
      hookSeesOrigin += 1;
      // The capability-gated admission must refuse any capability an observer
      // can produce (it holds the live origin scope object, which no public
      // surface exposes).
      if (admit({}) === true || admit(undefined) === true) takeSucceeded += 1;
      if (attackedSession !== '') return;
      attackedSession = String(origin.sessionId);
      attackDone = (async () => {
        const chunks: StreamChunk[] = [];
        for await (const chunk of deployment.llm.stream({
          provider: MOCK_PROVIDER, model: MOCK_MODEL, maxTokens: 64, messages: [],
          sessionId: attackedSession as unknown as SessionId,
        } as GenerateOptions)) chunks.push(chunk);
        attackChunks = chunks;
        // The module-level trusted entry without the live scope object must
        // not grant the trusted path either (its admission is object-identity
        // verified inside dsh-agent-loop).
        const runEntry = llmMod.runLoopDispatch;
        if (typeof runEntry === 'function') {
          for await (const chunk of runEntry({
            provider: MOCK_PROVIDER, model: MOCK_MODEL, maxTokens: 64, messages: [],
            sessionId: attackedSession as unknown as SessionId,
          } as GenerateOptions, undefined, {})) chunks.push(chunk);
        }
      })();
    },
  });
  hook.enable();
  try {
    const delegation = await delegate(new AbortController().signal);
    const outcome = await delegation.result;
    await delegation.dispose();
    await attackDone;
    assert.ok(hookSeesOrigin > 0, 'the observer must have seen the live origin through the public peek');
    assert.equal(takeSucceeded, 0, 'the capability-gated admission must never accept an observer-produced capability');
    assert.ok(attackChunks.some((chunk) =>
      chunk.type === 'finish' && typeof chunk.reason !== 'string' && chunk.reason.kind === 'error'
      && String(chunk.reason.failure.code) === 'dispatch_origin_unproven'),
      `the observer's dispatch must be refused by name: ${JSON.stringify(attackChunks)}`);
    assert.equal(String((outcome as { stopReason?: string }).stopReason), 'completed',
      `the legal child must complete despite the observer: ${JSON.stringify(outcome)}`);
    const events = recorder.events.slice(eventsBefore);
    assert.deepEqual(events.map((event) => event.kind), ['reserve', 'dispatch', 'settle'],
      `only the legal child is accounted: ${JSON.stringify(events)}`);
    assert.equal(adapterDispatches.length - before, 1, 'only the legal child reaches the adapter');
  } finally {
    hook.disable();
    adapterMode = 'normal';
  }
});

const C23_PROVIDER = 'c2p-h04-c23-mock';
const C23_MODEL = 'h04-c23-model';

/** A plain adapter for the C23 custom-iterator construction probe. */
class C23Adapter extends LlmAdapter {
  readonly calls: string[] = [];
  override providerInfo(provider: string): { id: string; name: string } {
    return { id: provider, name: `h04 c23 mock (${provider})` };
  }
  override async listModels(): Promise<never[]> { return []; }
  override async resolveModel(provider: string, model: string) {
    return { provider, id: model, name: `H04 c23 ${model}`, context: { contextWindow: 8192 }, defaultMaxTokens: 512 };
  }
  override async prepareCall(provider: string, model: string) {
    return { model: await this.resolveModel(provider, model), stream: (options: GenerateOptions) => this.stream(options) };
  }
  override async *stream(options: GenerateOptions): AsyncIterable<StreamChunk> {
    this.calls.push(String(options.sessionId));
    yield { type: 'block-start', index: 0, blockType: 'text' };
    yield { type: 'text-delta', index: 0, text: 'ok' };
    yield { type: 'usage', usage: { inputTokens: 2, outputTokens: 1 } };
    yield { type: 'finish', reason: { kind: 'stop' } };
  }
}

test('C22: a forwarding Proxy returned by the public service resolver cannot steal the loop capability', async () => {
  adapterMode = 'normal';
  const loopMod = (await import('@deepseek-ai/dsh-agent-loop')) as unknown as {
    admitLoopDispatchOrigin?: (capability: unknown) => boolean;
  };
  let proxyCalls = 0;
  let proxyAdmissions = 0;
  let stopProxy: (() => void) | undefined;
  const before = adapterDispatches.length;
  const eventsBefore = recorder.events.length;
  try {
    // The public service resolver (cordis internal/get) returns whatever the
    // outermost listener returns: a forwarding Proxy around the resolved
    // service. Its method wrappers observe the loop's arguments — but the
    // loop's own dispatch never goes through the resolver, so the capability
    // never appears there and the admission cannot be stolen.
    stopProxy = deployment.on('internal/get', (((_ctx: unknown, prop: unknown, _error: unknown, next: () => unknown) => {
      const resolved = next();
      if (prop !== 'llm' || typeof resolved !== 'object' || resolved === null) return resolved;
      return new Proxy(resolved as object, {
        get(target, key, receiver) {
          const value = Reflect.get(target, key, receiver);
          if (typeof value === 'function') {
            return (...args: unknown[]) => {
              proxyCalls += 1;
              if (typeof loopMod.admitLoopDispatchOrigin === 'function' && loopMod.admitLoopDispatchOrigin(args[2]) === true) {
                proxyAdmissions += 1;
              }
              return Reflect.apply(value, target, args);
            };
          }
          return value;
        },
      });
    }) as never));
    const delegation = await delegate(new AbortController().signal);
    const outcome = await delegation.result;
    await delegation.dispose();
    assert.ok(proxyCalls > 0, 'the resolver proxy must have observed the prepared-call surface');
    assert.equal(proxyAdmissions, 0, 'the observer must never admit the loop origin');
    assert.equal(String((outcome as { stopReason?: string }).stopReason), 'completed',
      `the legal child must complete despite the forwarding proxy: ${JSON.stringify(outcome)}`);
    const events = recorder.events.slice(eventsBefore);
    assert.deepEqual(events.map((event) => event.kind), ['reserve', 'dispatch', 'settle'],
      `only the legal child is accounted: ${JSON.stringify(events)}`);
    assert.equal(adapterDispatches.length - before, 1, 'only the legal child reaches the adapter');
  } finally {
    stopProxy?.();
  }
});

test('C23: a caller-provided custom Symbol.asyncIterator is constructed inside the cleared scope', async () => {
  adapterMode = 'normal';
  const c23 = new C23Adapter();
  deployment.llm.registerAdapter([C23_PROVIDER], c23);
  const loopMod = (await import('@deepseek-ai/dsh-agent-loop')) as unknown as {
    peekLoopDispatchOrigin?: () => { readonly sessionId: string; readonly signal: AbortSignal } | undefined;
  };
  let iteratorSeesOrigin: boolean | undefined;
  let stopCustom: (() => void) | undefined;
  let attackDone: Promise<void> = Promise.resolve();
  // The listener-provided custom iterable: its Symbol.asyncIterator factory
  // runs when the runtime retrieves the iterator during the isolated
  // construction, and must observe no origin there.
  stopCustom = deployment.on('llm/stream', ((request: GenerateOptions, next: () => AsyncIterable<StreamChunk>) => {
    if (request.provider !== C23_PROVIDER) return next();
    const peek = loopMod.peekLoopDispatchOrigin;
    return {
      [Symbol.asyncIterator]: () => {
        iteratorSeesOrigin = typeof peek === 'function' && peek() !== undefined;
        return (next() as AsyncIterable<StreamChunk>)[Symbol.asyncIterator]();
      },
    };
  }) as never);
  const before = adapterDispatches.length;
  const eventsBefore = recorder.events.length;
  try {
    const delegationPromise = delegate(new AbortController().signal);
    await new Promise<void>((resolve) => {
      const stop = deployment.on('llm/stream', ((request: GenerateOptions, next: () => AsyncIterable<StreamChunk>) => {
        if (request.provider !== MOCK_PROVIDER) return next();
        // Inside the loop's live origin scope: a public dispatch to another
        // provider. The runtime must isolate its whole construction — the
        // listener-provided custom Symbol.asyncIterator retrieval included —
        // so the factory observes no origin (acceptance PC-2).
        attackDone = (async () => {
          const chunks: StreamChunk[] = [];
          for await (const chunk of deployment.llm.stream({
            provider: C23_PROVIDER, model: C23_MODEL, maxTokens: 64,
            messages: [{ role: 'user', content: [{ type: 'text', text: 'custom iterator probe' }] }],
          })) chunks.push(chunk);
          if (!chunks.some((chunk) => chunk.type === 'finish' && typeof chunk.reason !== 'string' && chunk.reason.kind === 'stop')) {
            throw new Error('the custom-iterator probe dispatch did not complete');
          }
        })();
        void attackDone;
        resolve();
        return next();
      }) as never);
      void stop;
    });
    const delegation = await delegationPromise;
    const outcome = await delegation.result;
    await delegation.dispose();
    await attackDone;
    assert.equal(iteratorSeesOrigin, false,
      `the listener-provided custom iterator retrieval must see no origin inside the cleared scope: ${String(iteratorSeesOrigin)}`);
    assert.equal(c23.calls.length, 1, 'the custom-iterator probe dispatch reaches its own provider once');
    assert.equal(String((outcome as { stopReason?: string }).stopReason), 'completed',
      `the legal child must still complete: ${JSON.stringify(outcome)}`);
    const events = recorder.events.slice(eventsBefore);
    assert.deepEqual(events.map((event) => event.kind), ['reserve', 'dispatch', 'settle'],
      `only the legal child is accounted: ${JSON.stringify(events)}`);
    assert.equal(adapterDispatches.length - before, 1, 'only the legal child reaches the protected adapter');
  } finally {
    stopCustom?.();
    adapterMode = 'normal';
  }
});

test('C24: public boolean controls, public methods, or unproven callers cannot mint trusted loop dispatch', async () => {
  const loopMod = (await import('@deepseek-ai/dsh-agent-loop')) as unknown as {
    peekLoopDispatchOrigin?: () => { readonly sessionId: string; readonly signal: AbortSignal } | undefined;
  };
  const llmMod = (await import('@deepseek-ai/dsh-llm')) as unknown as {
    runLoopDispatch?: (options: GenerateOptions, preparedCall: unknown, capability: unknown) => AsyncIterable<StreamChunk>;
  };

  for (const mode of ['normal', 'no-adapter-once'] as const) {
    adapterMode = mode;
    const before = adapterDispatches.length;
    const eventsBefore = recorder.events.length;
    let attackInitiated = false;
    const attackResults: Promise<{ chunks: StreamChunk[]; originFailures: number }>[] = [];

    const stopAttack = deployment.on('llm/stream', ((request: GenerateOptions, next: () => AsyncIterable<StreamChunk>) => {
      if (request.provider === MOCK_PROVIDER && !attackInitiated) {
        attackInitiated = true;
        const fakeRequest = {
          ...request,
          messages: [{ role: 'user', content: [{ type: 'text', text: 'unauthorized substituted payload' }] }],
        } as GenerateOptions;
        const snapshot = typeof loopMod.peekLoopDispatchOrigin === 'function' ? loopMod.peekLoopDispatchOrigin() : undefined;
        const service = deployment.llm as unknown as {
          streamWithRegistration?: (options: GenerateOptions, prepared?: unknown, trusted?: boolean) => AsyncIterable<StreamChunk>;
        };

        const executeAndCollect = async (iter: AsyncIterable<StreamChunk>) => {
          const chunks: StreamChunk[] = [];
          for await (const chunk of iter) chunks.push(chunk);
          const originFailures = chunks.filter((c) =>
            c.type === 'finish' && typeof c.reason !== 'string' && c.reason.kind === 'error'
            && String(c.reason.failure.code) === 'dispatch_origin_unproven',
          ).length;
          return { chunks, originFailures };
        };

        // 1. Calling public deployment.llm.stream with fake request
        attackResults.push(executeAndCollect(deployment.llm.stream(fakeRequest)));

        // 2. Calling streamWithRegistration with boolean true / public call
        if (typeof service.streamWithRegistration === 'function') {
          attackResults.push(executeAndCollect(service.streamWithRegistration(fakeRequest, undefined, true)));
        }

        // 3. Calling runLoopDispatch with public snapshot or fake capability
        if (typeof llmMod.runLoopDispatch === 'function') {
          attackResults.push(executeAndCollect(llmMod.runLoopDispatch(fakeRequest, undefined, snapshot)));
          attackResults.push(executeAndCollect(llmMod.runLoopDispatch(fakeRequest, undefined, {})));
        }
      }
      return next();
    }) as never);

    try {
      const delegation = await delegate(new AbortController().signal);
      const outcome = await delegation.result;
      await delegation.dispose();
      const attacks = await Promise.all(attackResults);

      assert.ok(attackInitiated, `attack must be triggered for mode ${mode}`);
      assert.ok(attacks.length >= 3, `at least 3 attack attempts expected for mode ${mode}`);
      assert.ok(attacks.every((a) => a.originFailures > 0), `all attack attempts must fail closed with dispatch_origin_unproven in mode ${mode}`);
      assert.equal(String((outcome as { stopReason?: string }).stopReason), 'completed');

      const events = recorder.events.slice(eventsBefore);
      assert.deepEqual(events.map((event) => event.kind), ['reserve', 'dispatch', 'settle'],
        `only the legal child is accounted: ${JSON.stringify(events)}`);
      assert.equal(adapterDispatches.length - before, 1, `only the legal child reaches the adapter in mode ${mode}`);
      const dispatchedPayloads = adapterDispatches.slice(before).map((d: any) => d.messages);
      assert.ok(!JSON.stringify(dispatchedPayloads).includes('unauthorized substituted payload'),
        'unauthorized substituted payload must never reach adapter');
    } finally {
      stopAttack();
      adapterMode = 'normal';
    }
  }
});

test('C25: resolver Proxy wrapping all members along the dispatch path cannot hijack or mint dispatch authority (prepared and fallback)', async () => {
  const loopMod = (await import('@deepseek-ai/dsh-agent-loop')) as unknown as {
    admitLoopDispatchOrigin?: (capability: unknown) => boolean;
  };
  let proxyInterceptions = 0;
  let unauthorizedAdmissions = 0;
  const interceptedMethods: string[] = [];

  const stopProxy = deployment.on('internal/get', (((_ctx: unknown, prop: unknown, _error: unknown, next: () => unknown) => {
    const resolved = next();
    if (prop !== 'llm' || typeof resolved !== 'object' || resolved === null) return resolved;
    return new Proxy(resolved as object, {
      get(target, key, receiver) {
        const val = Reflect.get(target, key, receiver);
        if (typeof val === 'function') {
          return (...args: unknown[]) => {
            proxyInterceptions += 1;
            interceptedMethods.push(String(key));
            for (const arg of args) {
              if (typeof loopMod.admitLoopDispatchOrigin === 'function' && loopMod.admitLoopDispatchOrigin(arg) === true) {
                unauthorizedAdmissions += 1;
              }
            }
            return Reflect.apply(val, target, args);
          };
        }
        return val;
      },
    });
  }) as never));

  try {
    for (const mode of ['normal', 'no-adapter-once'] as const) {
      adapterMode = mode;
      const before = adapterDispatches.length;
      const eventsBefore = recorder.events.length;
      const interceptionsBefore = proxyInterceptions;

      const delegation = await delegate(new AbortController().signal);
      const outcome = await delegation.result;
      await delegation.dispose();

      assert.ok(proxyInterceptions > interceptionsBefore, `the resolver proxy must observe member accesses in mode ${mode}`);
      assert.equal(unauthorizedAdmissions, 0, `proxy interception must never yield origin admission in mode ${mode}`);
      assert.equal(String((outcome as { stopReason?: string }).stopReason), 'completed',
        `the legal child must complete despite proxy interception in mode ${mode}: ${JSON.stringify(outcome)}`);
      const events = recorder.events.slice(eventsBefore);
      assert.deepEqual(events.map((event) => event.kind), ['reserve', 'dispatch', 'settle'],
        `only the legal child is accounted in mode ${mode}: ${JSON.stringify(events)}`);
      assert.equal(adapterDispatches.length - before, 1, `only legal child reaches adapter in mode ${mode}`);
    }
  } finally {
    stopProxy();
    adapterMode = 'normal';
  }
});

async function createFullDeployment(label: string) {
  const profile = loadProfileDirectory(`h04-cancel-${label}`, profileDir, installAnchor);
  const patches = [
    ...profile.layers.flatMap((layer) => layer.patches),
    ...profile.patches,
    ...loadOverlayPatches(`h04-cancel-${label}`, policyFile),
  ];
  const configDir = path.join(privateRoot, `cfg-${label}`);
  mkdirSync(configDir, { recursive: true });
  const config = path.join(configDir, 'cordis.yml');
  writeFileSync(config, readFileSync(path.join(profileDir, 'cordis.yml')));

  const dep = await boot(`h04-cancel-${label}`, config, patches, (hostCtx: Context) => {
    provideCmdline(hostCtx, { args: ['--host', '127.0.0.1', '--port', '0', '--no-open'], exit: () => {} });
  });

  const adapter = new CountingAdapter(label);
  dep.llm.registerAdapter([MOCK_PROVIDER], adapter);

  const depRecorder = new ControllableRecorder();
  const depBridge = dep.get('code2paperBridge') as unknown as { hostGeneration: number };
  const depBindings = new sessionModule.SessionBindings({
    caller: { executionId: `h04-${label}-exec`, runId: `h04-${label}-run`, hostGeneration: depBridge.hostGeneration },
    recorder: depRecorder as unknown as import('../src/session-binding.js').ClaimRecorder,
  });
  dispatchModule.registerCode2PaperSpawn(dep, { bindings: depBindings });
  const sessionId = `h04-${label}-root-${runId}` as SessionId;
  const depRoot = await sessionModule.createBoundRootAgent(dep, {
    bindings: depBindings,
    sessionId,
    task: { taskId: `task-h04-${label}`, epoch: 1 },
    cwd: path.join(privateRoot, 'workspace'),
  });

  accounting.installRequestAccounting(dep, {
    bindings: depBindings,
    recorder: depRecorder,
    route: MOCK_PROVIDER,
    purpose: 'writer',
    outputCap: { version: 'h04-test-cap/1', cap: () => 512 },
  });

  let disposed = false;
  return {
    label,
    sessionId,
    deployment: dep,
    recorder: depRecorder,
    bindings: depBindings,
    root: depRoot,
    adapter,
    async delegate(signal: AbortSignal) {
      const dispatched = await dispatchModule.dispatchRole(dep, {
        parent: depRoot.handle.agent,
        role: 'writer',
        prompt: [{ type: 'text', text: `${label} probe` }],
        signal,
        bindings: depBindings,
        agentOptions: { provider: MOCK_PROVIDER, model: MOCK_MODEL, maxTokens: 64 },
      });
      return { result: dispatched.run.result, dispose: () => dispatched.run.dispose() };
    },
    async dispose() {
      if (disposed) return;
      disposed = true;
      try { await depRoot.dispose(); } catch {}
      try { await dep.fiber.dispose(); } catch {}
    },
  };
}

test('C26: concurrent dual-deployment: prepared dispatches route to respective runtimes without cross-dispatch; ambiguous fallback fails closed; post-disposal recovers', async () => {
  // Deployment A is the top-level deployment booted in before()
  const envB = await createFullDeployment('c26-b');

  try {
    // 1. Both A and B are active. Prepared dispatches on both run concurrently.
    // They must route strictly to their own runtime and adapter, with zero cross-runtime pollution.
    adapterMode = 'normal';
    adapterLabel = 'c26-dual';
    const beforeA = recorder.events.length;
    const beforeB = envB.recorder.events.length;
    const beforeGlobalDispatches = adapterDispatches.length;

    const delA = await delegate(new AbortController().signal);
    const delB = await envB.delegate(new AbortController().signal);
    const [outcomeA, outcomeB] = await Promise.all([delA.result, delB.result]);
    await Promise.all([delA.dispose(), delB.dispose()]);

    assert.equal(String((outcomeA as { stopReason?: string }).stopReason), 'completed', 'prepared dispatch on deployment A must complete');
    assert.equal(String((outcomeB as { stopReason?: string }).stopReason), 'completed', 'prepared dispatch on deployment B must complete');

    // Check accounting events on both recorders
    const eventsA = recorder.events.slice(beforeA);
    const eventsB = envB.recorder.events.slice(beforeB);
    assert.deepEqual(eventsA.map((e) => e.kind), ['reserve', 'dispatch', 'settle'], 'deployment A accounted independently');
    assert.deepEqual(eventsB.map((e) => e.kind), ['reserve', 'dispatch', 'settle'], 'deployment B accounted independently');

    // Check adapter dispatches belong to their respective deployments
    const newDispatches = adapterDispatches.slice(beforeGlobalDispatches);
    assert.equal(newDispatches.length, 2, 'exactly two adapter dispatches for two concurrent deployments');
    const dispatchA = newDispatches.find((d) => d.label === 'c26-dual');
    const dispatchB = newDispatches.find((d) => d.label === 'c26-b:c26-dual');
    assert.ok(dispatchA !== undefined, 'deployment A prepared dispatch arrived at A adapter');
    assert.ok(dispatchB !== undefined, 'deployment B prepared dispatch arrived at B adapter');
    assert.notEqual(dispatchA.sessionId, dispatchB.sessionId, 'distinct sessions across deployments');
    assert.ok(!newDispatches.some((d) => d.label === 'c26-b:c26-dual' && d.sessionId === dispatchA.sessionId), 'no cross-dispatch from B to A');
    assert.ok(!newDispatches.some((d) => d.label === 'c26-dual' && d.sessionId === dispatchB.sessionId), 'no cross-dispatch from A to B');

    // 2. Fallback direct dispatch on A fails closed because dual active deployments make fallback ambiguous
    adapterMode = 'no-adapter-once';
    const beforeFail = adapterDispatches.length;
    const eventsBeforeFail = recorder.events.length;
    const delFailA = await delegate(new AbortController().signal);
    const outcomeFailA = await delFailA.result;
    await delFailA.dispose();

    assert.notEqual((outcomeFailA as { stopReason?: string }).stopReason, 'completed',
      'concurrent dual-deployment fallback must fail closed on deployment A');
    assert.equal(adapterDispatches.length - beforeFail, 0, 'zero adapter dispatch on ambiguous dual fallback');
    assert.ok(!recorder.events.slice(eventsBeforeFail).some((e) => e.kind === 'settle' && e.detail === 'settled'), 'failed fallback must not settle');

    // Same check on deployment B
    const beforeFailB = adapterDispatches.length;
    const eventsBeforeFailB = envB.recorder.events.length;
    const delFailB = await envB.delegate(new AbortController().signal);
    const outcomeFailB = await delFailB.result;
    await delFailB.dispose();

    assert.notEqual((outcomeFailB as { stopReason?: string }).stopReason, 'completed',
      'concurrent dual-deployment fallback must fail closed on deployment B');
    assert.equal(adapterDispatches.length - beforeFailB, 0, 'zero adapter dispatch on ambiguous dual fallback on B');
    assert.ok(!envB.recorder.events.slice(eventsBeforeFailB).some((e) => e.kind === 'settle' && e.detail === 'settled'), 'failed fallback must not settle');
  } finally {
    // Dispose deployment B
    await envB.dispose();
  }

  // 3. Repeated disposal of deployment B is safe and idempotent
  await envB.dispose();

  // 4. Once deployment B is disposed, deployment A is the sole active deployment.
  // Both prepared and fallback dispatches must succeed cleanly on deployment A.
  for (const mode of ['normal', 'no-adapter-once'] as const) {
    adapterMode = mode;
    const before = adapterDispatches.length;
    const eventsBefore = recorder.events.length;
    const del = await delegate(new AbortController().signal);
    const outcome = await del.result;
    await del.dispose();

    assert.equal(String((outcome as { stopReason?: string }).stopReason), 'completed',
      `post-disposal sole active deployment A must complete in mode ${mode}: ${JSON.stringify(outcome)}`);
    assert.equal(adapterDispatches.length - before, 1, `post-disposal legal dispatch reaches adapter once in mode ${mode}`);
    const events = recorder.events.slice(eventsBefore);
    assert.ok(events.some((e) => e.kind === 'settle' && e.detail === 'settled'),
      `deployment A accounted properly: ${JSON.stringify(events)}`);
  }
  adapterMode = 'normal';
});

test('C27: deployment lifecycle sequence: destroy A -> create B -> B prepared & fallback both succeed; repeated disposal of A is safe', async () => {
  // Step 1: Deployment A runs normal prepared dispatch
  adapterMode = 'normal';
  const beforeA = adapterDispatches.length;
  const eventsBeforeA = recorder.events.length;

  const delA = await delegate(new AbortController().signal);
  const outcomeA = await delA.result;
  await delA.dispose();

  assert.equal(String((outcomeA as { stopReason?: string }).stopReason), 'completed', 'deployment A prepared dispatch must complete');
  assert.equal(adapterDispatches.length - beforeA, 1, 'deployment A reaches adapter once');
  const eventsA = recorder.events.slice(eventsBeforeA);
  assert.deepEqual(eventsA.map((e) => e.kind), ['reserve', 'dispatch', 'settle'], 'deployment A accounts reserve/dispatch/settle');

  // Step 2: Destroy deployment A completely
  await root.dispose();
  await deployment.fiber.dispose();
  // Repeated disposal of A is safe
  await deployment.fiber.dispose();

  // Step 3: Boot deployment B as sole deployment
  const envB = await createFullDeployment('c27-seq-b');
  try {
    // Step 4: Run prepared dispatch on B
    adapterMode = 'normal';
    const beforeB1 = adapterDispatches.length;
    const eventsBeforeB1 = envB.recorder.events.length;

    const delB1 = await envB.delegate(new AbortController().signal);
    const outcomeB1 = await delB1.result;
    await delB1.dispose();

    assert.equal(String((outcomeB1 as { stopReason?: string }).stopReason), 'completed', 'deployment B prepared dispatch must complete');
    assert.equal(adapterDispatches.length - beforeB1, 1, 'deployment B prepared dispatch reaches adapter once');
    const eventsB1 = envB.recorder.events.slice(eventsBeforeB1);
    assert.deepEqual(eventsB1.map((e) => e.kind), ['reserve', 'dispatch', 'settle'], 'deployment B prepared accounts reserve/dispatch/settle');

    // Step 5: Run fallback dispatch on B
    adapterMode = 'no-adapter-once';
    const beforeB2 = adapterDispatches.length;
    const eventsBeforeB2 = envB.recorder.events.length;

    const delB2 = await envB.delegate(new AbortController().signal);
    const outcomeB2 = await delB2.result;
    await delB2.dispose();

    assert.equal(String((outcomeB2 as { stopReason?: string }).stopReason), 'completed', 'deployment B fallback dispatch must complete');
    assert.equal(adapterDispatches.length - beforeB2, 1, 'deployment B fallback dispatch reaches adapter once');
    const eventsB2 = envB.recorder.events.slice(eventsBeforeB2);
    assert.deepEqual(eventsB2.map((e) => e.kind), ['reserve', 'dispatch', 'settle'], 'deployment B fallback accounts reserve/dispatch/settle');
  } finally {
    await envB.dispose();
    adapterMode = 'normal';
  }
});

